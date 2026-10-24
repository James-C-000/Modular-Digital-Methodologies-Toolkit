"""A RAG chat session: index + retrieval + grounded, cited, streamed answers.

    session = RagSession(RagSettings(documents_dir=..., llm_path=...))
    session.build_index(on_progress)
    answer = session.ask("Who was the harbour master?", on_token=print)

Retrieval: BM25 + dense (multilingual-e5-small) fused with Reciprocal Rank
Fusion, then the top candidates are reranked with a cross-encoder
(bge-reranker-v2-m3, optional) and the best `top_k` go to the LLM as numbered
context.  Follow-up questions are first rewritten into standalone queries.
"""
import logging
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
    strip_echoed_instructions,
)


log = logging.getLogger("mdmt.rag")

# A plain answer is short.  With thinking on, the model may use all the room
# left in the context: Qwen3.5-2B reasoned for 3,000-9,000 tokens on eval
# questions, so 32768 is the recommended context length for thinking mode.
ANSWER_TOKENS = 768
THINKING_CONTEXT = 32768


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
        """Room kept free for the reply when deciding how many passages fit."""
        return 4096 if self.enable_thinking else ANSWER_TOKENS


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
    cut_off: bool = False                  # generation ran out of room before finishing
    cut_off_while_thinking: bool = False   # ... and before it started the answer
    dropped_citations: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)


def cut_off_advice(answer, settings) -> str | None:
    """What to tell the user when *answer* ran out of room, or None."""
    if not answer.cut_off:
        return None
    if settings.enable_thinking:
        what = ("RAGBot ran out of room while reasoning, before it could answer."
                if answer.cut_off_while_thinking else "This answer was cut off: RAGBot ran out of room.")
        longer = (f"Increase the Context length (now {settings.n_ctx}) to {THINKING_CONTEXT} with Change setup,"
                  " and ask again." if settings.n_ctx < THINKING_CONTEXT else
                  "Increase the Context length further with Change setup, and ask again.")
        return (f"{what} Thinking can use many thousands of tokens. {longer} A longer context needs more memory;"
                " if your computer does not have enough, turn off Thinking mode instead.")
    return ("This answer was cut off at RAGBot's length limit. Try a narrower question, or start a New"
            " conversation if this one is long.")


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
        self.notice = None   # something the user should know about this session
        self.llm = llm if llm is not None else self._load_llm(settings)
        self.history: list[tuple[str, str]] = []
        self._busy = threading.Lock()

    def _load_llm(self, settings):
        """Load the chat model; if it does not fit on the GPU, run it on the CPU."""
        from RAG import generation
        try:
            return generation.LlmEngine(settings.llm_path, n_ctx=settings.n_ctx, n_threads=settings.threads,
                                        n_gpu_layers=settings.n_gpu_layers)
        except Exception as e:
            if not settings.n_gpu_layers:
                raise
            log.warning("loading the model on the GPU failed (%s); using the CPU", e)
            settings.n_gpu_layers = 0
            self.notice = ("The model did not fit in the GPU's memory, so it runs on the CPU, which is slower."
                           " A shorter Context length, or the 2B model, may fit on the GPU.")
            return generation.LlmEngine(settings.llm_path, n_ctx=settings.n_ctx, n_threads=settings.threads,
                                        n_gpu_layers=0)

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
            room = max(16, self.settings.n_ctx - self.llm.count_tokens(prompt) - 8)
            max_tokens = room if thinking_mode else min(ANSWER_TOKENS, room)
            for piece in self.llm.stream(prompt, thinking_mode, max_tokens, stop_event):
                raw += piece
                if on_token:
                    thinking, answer = split_thinking(raw, started_in_thinking=thinking_mode)
                    for kind, text in (("thinking", thinking), ("answer", answer)):
                        if len(text) > shown[kind]:
                            on_token(kind, text[shown[kind]:])
                            shown[kind] = len(text)
            timings["generation_s"] = time.perf_counter() - t
            stopped = bool(stop_event is not None and stop_event.is_set())
            cut_off = not stopped and getattr(self.llm, "last_finish_reason", None) == "length"

            thinking, answer = split_thinking(raw, started_in_thinking=thinking_mode)
            text, cited, dropped = parse_citations(strip_echoed_instructions(answer), len(context))
            by_number = {c.number: c for c in context}
            result = Answer(
                text=text, thinking=thinking, citations=[by_number[n] for n in cited], context=context,
                query=query, not_found=is_not_found(text), stopped=stopped, dropped_citations=dropped,
                cut_off=cut_off, cut_off_while_thinking=cut_off and thinking_mode and "</think>" not in raw,
                timings={k: round(v, 2) for k, v in timings.items()},
            )
            # Refusals stay out of the history: nothing in them can be referred
            # to, and small models otherwise answer the old question again.
            if text and not stopped and not cut_off and not result.not_found:
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
