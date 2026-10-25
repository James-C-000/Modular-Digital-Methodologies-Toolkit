"""RagSession with stand-in models (no downloads)."""
import threading

import pytest

from RAG.prompting import NOT_FOUND
from RAG.session import Busy, RagSession, RagSettings
from tests.test_rag_index import FakeEmbedder


class FakeLlm:
    """Records prompts; replies with a scripted answer, streamed in pieces."""

    def __init__(self, reply="The brig came from Lisbon [1][9].", rewrite="Endeavour cargo Lisbon"):
        self.reply, self.rewrite = reply, rewrite
        self.prompts, self.completions = [], []

    def render(self, messages, enable_thinking):
        return "\n".join(f"<{m['role']}>{m['content']}" for m in messages) + ("<think>" if enable_thinking else "")

    def count_tokens(self, text):
        return len(text.split())

    finish = "stop"       # what llama.cpp reports at the end: "stop" or "length"

    def stream(self, prompt, enable_thinking, max_tokens, stop_event=None):
        self.prompts.append(prompt)
        self.max_tokens = max_tokens
        self.last_finish_reason = None
        for i in range(0, len(self.reply), 5):
            if stop_event is not None and stop_event.is_set():
                break
            yield self.reply[i:i + 5]
        else:
            self.last_finish_reason = self.finish

    def complete(self, prompt, max_tokens=128):
        self.completions.append(prompt)
        return self.rewrite


class FakeReranker:
    def score(self, query, passages):
        # Prefer passages mentioning the mill, to prove reranking reorders.
        return [10.0 if "mill" in p else 0.0 for p in passages]


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "ships.txt").write_text("The brig Endeavour arrived from Lisbon carrying cork.", encoding="utf-8")
    (d / "mill.txt").write_text("The mill flooded in 1751 and grain prices rose.", encoding="utf-8")
    return d


def _session(docs, tmp_path, llm=None, rerank=False, **kw):
    s = RagSession(RagSettings(str(docs), "unused.gguf", rerank=rerank, **kw), embedder=FakeEmbedder(),
                   reranker=FakeReranker(), llm=llm or FakeLlm(), index_root=str(tmp_path / "index"))
    s.build_index()
    return s


def test_answer_is_streamed_cited_and_validated(docs, tmp_path):
    session = _session(docs, tmp_path)
    streamed = []
    answer = session.ask("Where did the Endeavour come from?", on_token=lambda kind, t: streamed.append((kind, t)))
    assert "".join(t for k, t in streamed if k == "answer") == "The brig came from Lisbon [1][9]."
    assert answer.text == "The brig came from Lisbon [1]."       # [9] is out of range
    assert answer.dropped_citations == [9]
    assert [c.number for c in answer.citations] == [1]
    assert answer.citations[0] is answer.context[0]  # [1] refers to the first context chunk
    assert session.history == [("Where did the Endeavour come from?", answer.text)]


def test_first_question_is_not_rewritten_but_follow_ups_are(docs, tmp_path):
    llm = FakeLlm()
    session = _session(docs, tmp_path, llm=llm)
    first = session.ask("Where did the Endeavour come from?")
    assert first.query == "Where did the Endeavour come from?" and not llm.completions
    second = session.ask("What did it carry?")
    assert second.query == "Endeavour cargo Lisbon"
    assert "Where did the Endeavour come from?" in llm.completions[0]
    assert "What did it carry?" in llm.prompts[-1]


def test_reranker_reorders_the_context(docs, tmp_path):
    session = _session(docs, tmp_path, rerank=True)
    context = session.retrieve("Endeavour Lisbon")
    assert context[0].chunk.file == "mill.txt" and context[0].score == 10.0
    assert [c.number for c in context] == [1, 2]


def test_not_found_answers_are_flagged(docs, tmp_path):
    session = _session(docs, tmp_path, llm=FakeLlm(reply=NOT_FOUND))
    answer = session.ask("Who was the king of France?")
    assert answer.not_found and answer.citations == []


def test_paraphrased_not_found_answers_are_flagged(docs, tmp_path):
    session = _session(docs, tmp_path, llm=FakeLlm(reply="None of the documents mention the king of France."))
    assert session.ask("Who was the king of France?").not_found


def test_thinking_is_separated_from_the_answer(docs, tmp_path):
    llm = FakeLlm(reply="Ship records say Lisbon.</think>\n\nLisbon [1].")
    session = _session(docs, tmp_path, llm=llm, enable_thinking=True)
    kinds = []
    answer = session.ask("Where from?", on_token=lambda kind, t: kinds.append(kind))
    assert answer.thinking == "Ship records say Lisbon." and answer.text == "Lisbon [1]."
    assert kinds.index("answer") > kinds.index("thinking")


def test_stop_ends_generation_and_keeps_history_clean(docs, tmp_path):
    session = _session(docs, tmp_path, llm=FakeLlm(reply="x" * 200))
    stop = threading.Event()
    answer = session.ask("Where?", on_token=lambda kind, t: stop.set(), stop_event=stop)
    assert answer.stopped and len(answer.text) < 200 and session.history == []


def test_one_question_at_a_time(docs, tmp_path):
    session = _session(docs, tmp_path)
    session._busy.acquire()
    try:
        with pytest.raises(Busy):
            session.ask("Where?")
    finally:
        session._busy.release()


def test_context_is_trimmed_to_fit_the_window(docs, tmp_path):
    # Half of a short window is kept for the answer: 418 - 209 - 64 = 145 leaves room
    # for the prompt with one passage (138 words) but not two (149).
    session = _session(docs, tmp_path, n_ctx=418)
    answer = session.ask("Where?")
    assert len(answer.context) == 1


def test_old_turns_are_dropped_when_even_one_passage_does_not_fit(docs, tmp_path):
    """At a small Context length the history (up to 1500 tokens) once pushed the prompt past the window."""
    llm = FakeLlm()
    session = _session(docs, tmp_path, llm=llm, n_ctx=418)
    session.history = [("Who wrote the ledger?", "word " * 300), ("And when?", "In 1751.")]
    answer = session.ask("Where?")
    assert len(answer.context) == 1
    assert "word word" not in llm.prompts[-1] and "In 1751." in llm.prompts[-1]   # the oldest turn went first
    assert llm.count_tokens(llm.prompts[-1]) + llm.max_tokens <= 418


def test_a_question_too_long_for_the_window_is_refused_clearly(docs, tmp_path):
    from RAG.session import PromptTooLong
    session = _session(docs, tmp_path, n_ctx=418)
    with pytest.raises(PromptTooLong):
        session.ask("Where " * 400)


def test_the_index_is_not_updated_while_a_question_is_answered(docs, tmp_path):
    session = _session(docs, tmp_path)
    session._busy.acquire()
    try:
        with pytest.raises(Busy):
            session.build_index()
    finally:
        session._busy.release()


def test_not_found_turns_stay_out_of_the_conversation(docs, tmp_path):
    # A refusal carries nothing a follow-up could refer to, and small models
    # otherwise answer the earlier, unanswerable question again.
    llm = FakeLlm(reply=NOT_FOUND)
    session = _session(docs, tmp_path, llm=llm)
    session.ask("Who painted the Sistine Chapel?")
    assert session.history == []
    llm.reply = "The brig came from Lisbon [1]."
    session.ask("Where did the Endeavour come from?")
    assert not llm.completions          # nothing to rewrite against: no history
    assert "Sistine" not in llm.prompts[-1]


def test_echoed_instructions_do_not_reach_the_user(docs, tmp_path):
    from RAG.prompting import CITE_REMINDER
    session = _session(docs, tmp_path, llm=FakeLlm(reply="Lisbon [1].\n\n" + CITE_REMINDER))
    answer = session.ask("Where did the Endeavour come from?")
    assert answer.text == "Lisbon [1]." and not answer.not_found


def test_running_out_of_room_while_thinking_is_reported(docs, tmp_path):
    llm = FakeLlm(reply="The question asks where the brig came from. Document 1 says")   # no </think>
    llm.finish = "length"
    session = _session(docs, tmp_path, llm=llm, enable_thinking=True)
    answer = session.ask("Where did the Endeavour come from?")
    assert answer.text == "" and answer.cut_off and answer.cut_off_while_thinking
    assert session.history == []


def test_an_answer_cut_off_mid_sentence_is_reported(docs, tmp_path):
    llm = FakeLlm(reply="The brig came from Lisbon [1] and then sailed")
    llm.finish = "length"
    answer = _session(docs, tmp_path, llm=llm).ask("Where?")
    assert answer.cut_off and not answer.cut_off_while_thinking and answer.text


def test_a_normal_answer_is_not_cut_off(docs, tmp_path):
    answer = _session(docs, tmp_path).ask("Where?")
    assert not answer.cut_off


def test_thinking_may_use_all_the_room_left_in_the_context(docs, tmp_path):
    llm = FakeLlm(reply="Hmm.</think>Lisbon [1].")
    session = _session(docs, tmp_path, llm=llm, enable_thinking=True, n_ctx=32768)
    session.ask("Where?")
    assert llm.max_tokens > 30000                  # not capped at 4096
    llm = FakeLlm()
    _session(docs, tmp_path, llm=llm, n_ctx=32768).ask("Where?")
    assert llm.max_tokens == 768                   # plain answers stay short


def test_a_model_that_does_not_fit_on_the_gpu_runs_on_the_cpu(docs, tmp_path, monkeypatch):
    import RAG.generation as generation
    loads = []

    class SmallGpu(FakeLlm):
        def __init__(self, path, n_ctx, n_threads=None, n_gpu_layers=0):
            loads.append(n_gpu_layers)
            if n_gpu_layers:
                raise ValueError("Failed to create llama_context")   # what llama.cpp raises on GPU OOM
            super().__init__()

    monkeypatch.setattr(generation, "LlmEngine", SmallGpu)
    settings = RagSettings(str(docs), "model.gguf", n_gpu_layers=-1)
    session = RagSession(settings, embedder=FakeEmbedder(), index_root=str(tmp_path / "index"))
    assert loads == [-1, 0] and settings.n_gpu_layers == 0
    assert "CPU" in session.notice


def test_a_cpu_failure_is_not_retried(docs, tmp_path, monkeypatch):
    import RAG.generation as generation

    class Broken(FakeLlm):
        def __init__(self, *a, **k):
            raise ValueError("not a GGUF file")

    monkeypatch.setattr(generation, "LlmEngine", Broken)
    with pytest.raises(ValueError):
        RagSession(RagSettings(str(docs), "model.gguf"), embedder=FakeEmbedder(), index_root=str(tmp_path / "i"))
