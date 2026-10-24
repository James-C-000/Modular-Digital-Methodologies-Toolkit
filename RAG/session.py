"""A RAG chat session: index + retrieval + grounded, cited, streamed answers.

    session = RagSession(RagSettings(documents_dir=..., llm_path=...))
    session.build_index(on_progress)
    answer = session.ask("Who was the harbour master?", on_token=print)

Retrieval: BM25 + dense (multilingual-e5-small) fused with Reciprocal Rank
Fusion, then the top candidates are reranked with a cross-encoder
(bge-reranker-v2-m3, optional) and the best `top_k` go to the LLM as numbered
context.  Follow-up questions are first rewritten into standalone queries.
"""
import threading
import time
from dataclasses import dataclass, field

from RAG.prompting import (
    answer_messages,
    history_window,
    is_not_found,
    parse_citations,
    rewrite_messages,
    split_thinking,
)


@dataclass
class RagSettings:
    documents_dir: str
    llm_path: str
    n_ctx: int = 8192
    enable_thinking: bool = False
    rerank: bool = True
    candidates: int = 20          # fused candidates sent to the reranker
    top_k: int = 6                # chunks given to the LLM
    n_gpu_layers: int = 0
    threads: int | None = None
    history_budget: int = 1500    # tokens of conversation kept in the prompt

    @property
    def max_answer_tokens(self) -> int:
        return 4096 if self.enable_thinking else 768


@dataclass
class Citation:
    number: int
    chunk: object               # RAG.chunking.Chunk
    score: float | None = None  # reranker score, if reranked


@dataclass
class Answer:
    text: str
    thinking: str
    citations: list               # Citation, in first-cited order
    context: list                 # every Citation given to the model, numbered
    query: str                    # the (possibly rewritten) retrieval query
    not_found: bool = False
    stopped: bool = False
    dropped_citations: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)


class Busy(RuntimeError):
    """Raised when a question is asked while another is still being answered."""


class RagSession:
    def __init__(self, settings: RagSettings, embedder=None, reranker=None, llm=None, index_root=None):
        from RAG import models
        from RAG.index import CorpusIndex
        self.settings = settings
        self.embedder = embedder or models.get_embedder()
        self._reranker = reranker
        self.index = CorpusIndex(settings.documents_dir, self.embedder, index_root=index_root)
        if llm is None:
            from RAG.generation import LlmEngine
            llm = LlmEngine(settings.llm_path, n_ctx=settings.n_ctx, n_threads=settings.threads,
                            n_gpu_layers=settings.n_gpu_layers)
        self.llm = llm
        self.history: list[tuple[str, str]] = []
        self._busy = threading.Lock()

    # ------------------------------------------------------------ indexing ----

    def build_index(self, on_progress=None):
        return self.index.update(on_progress)

    @property
    def reranker(self):
        if self._reranker is None and self.settings.rerank:
            from RAG import models
            self._reranker = models.get_reranker()
        return self._reranker

    # ----------------------------------------------------------- retrieval ----

    def retrieve(self, query: str) -> list[Citation]:
        hits = self.index.search(query, k=self.settings.candidates)
        if self.settings.rerank and hits:
            scores = self.reranker.score(query, [h.chunk.text for h in hits])
            ranked = sorted(zip(hits, scores), key=lambda hs: -float(hs[1]))
            return [Citation(i, h.chunk, float(s)) for i, (h, s) in enumerate(ranked[:self.settings.top_k], 1)]
        return [Citation(i, h.chunk) for i, h in enumerate(hits[:self.settings.top_k], 1)]

    def standalone_query(self, question: str) -> str:
        """Rewrite a follow-up into a self-contained query (first questions pass through)."""
        if not self.history:
            return question
        prompt = self.llm.render(rewrite_messages(question, self.history), enable_thinking=False)
        rewritten = split_thinking(self.llm.complete(prompt, max_tokens=96))[1].strip().strip('"').strip()
        return rewritten.splitlines()[0] if rewritten else question

    # ------------------------------------------------------------- answers ----

    def _fit_context(self, question, context, history):
        """Drop the lowest-ranked chunks until the prompt fits the context window."""
        budget = self.settings.n_ctx - self.settings.max_answer_tokens - 64
        while True:
            prompt = self.llm.render(answer_messages(question, [c.chunk for c in context], history),
                                     self.settings.enable_thinking)
            if self.llm.count_tokens(prompt) <= budget or len(context) <= 1:
                return prompt, context
            context = context[:-1]

    def ask(self, question: str, on_token=None, stop_event=None) -> Answer:
        """Answer *question*.  on_token(kind, text) streams 'thinking'/'answer' text."""
        if not self._busy.acquire(blocking=False):
            raise Busy("a question is already being answered")
        try:
            timings, t0 = {}, time.perf_counter()
            query = self.standalone_query(question)
            timings["rewrite_s"] = time.perf_counter() - t0

            t = time.perf_counter()
            context = self.retrieve(query)
            timings["retrieval_s"] = time.perf_counter() - t

            history = history_window(self.history, self.settings.history_budget, self.llm.count_tokens)
            prompt, context = self._fit_context(question, context, history)

            t = time.perf_counter()
            raw, shown = "", {"thinking": 0, "answer": 0}
            thinking_mode = self.settings.enable_thinking
            for piece in self.llm.stream(prompt, thinking_mode, self.settings.max_answer_tokens, stop_event):
                raw += piece
                if on_token:
                    thinking, answer = split_thinking(raw, started_in_thinking=thinking_mode)
                    for kind, text in (("thinking", thinking), ("answer", answer)):
                        if len(text) > shown[kind]:
                            on_token(kind, text[shown[kind]:])
                            shown[kind] = len(text)
            timings["generation_s"] = time.perf_counter() - t
            stopped = bool(stop_event is not None and stop_event.is_set())

            thinking, answer = split_thinking(raw, started_in_thinking=thinking_mode)
            text, cited, dropped = parse_citations(answer, len(context))
            by_number = {c.number: c for c in context}
            result = Answer(
                text=text, thinking=thinking, citations=[by_number[n] for n in cited], context=context,
                query=query, not_found=is_not_found(text), stopped=stopped, dropped_citations=dropped,
                timings={k: round(v, 2) for k, v in timings.items()},
            )
            # Refusals stay out of the history: nothing in them can be referred
            # to, and small models otherwise answer the old question again.
            if text and not stopped and not result.not_found:
                self.history.append((question, text))
            return result
        finally:
            self._busy.release()

    @property
    def busy(self) -> bool:
        return self._busy.locked()

    def reset_conversation(self):
        self.history.clear()

    def close(self):
        if hasattr(self.llm, "close"):
            self.llm.close()
