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

    def stream(self, prompt, enable_thinking, max_tokens, stop_event=None):
        self.prompts.append(prompt)
        for i in range(0, len(self.reply), 5):
            if stop_event is not None and stop_event.is_set():
                break
            yield self.reply[i:i + 5]

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
    session = _session(docs, tmp_path, n_ctx=800)  # 768 answer tokens leave almost no room
    answer = session.ask("Where?")
    assert len(answer.context) == 1


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
