import json

import pytest

from RAG import qwen_rag
from tests.test_rag_session import FakeLlm, FakeReranker
from tests.test_rag_index import FakeEmbedder


def test_cli_answers_questions_as_json_lines(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ships.txt").write_text("The brig Endeavour arrived from Lisbon.", encoding="utf-8")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"x")
    real = qwen_rag.RagSession

    def fake_session(settings):
        return real(settings, embedder=FakeEmbedder(), reranker=FakeReranker(), llm=FakeLlm(),
                    index_root=str(tmp_path / "index"))

    monkeypatch.setattr(qwen_rag, "RagSession", fake_session)
    assert qwen_rag.main(["--documents", str(docs), "--llm", str(model), "--json",
                          "--question", "Where from?"]) == 0
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["question"] == "Where from?"
    assert record["answer"] == "The brig came from Lisbon [1]."
    assert record["citations"][0]["file"] == "ships.txt" and record["dropped_citations"] == [9]


def test_cli_rejects_missing_paths(tmp_path):
    with pytest.raises(SystemExit):
        qwen_rag.main(["--documents", str(tmp_path / "nope"), "--llm", "x.gguf"])


@pytest.mark.parametrize("args, expected", [
    ([], 8192),
    (["--enable-thinking"], 32768),
    (["--enable-thinking", "--context-window", "16384"], 16384),
])
def test_thinking_gets_a_long_context_unless_one_is_given(tmp_path, monkeypatch, args, expected):
    docs = tmp_path / "docs"
    docs.mkdir()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"x")
    seen = {}

    def fake_session(settings):
        seen["n_ctx"] = settings.n_ctx
        raise SystemExit(0)

    monkeypatch.setattr(qwen_rag, "RagSession", fake_session)
    with pytest.raises(SystemExit):
        qwen_rag.main(["--documents", str(docs), "--llm", str(model), *args])
    assert seen["n_ctx"] == expected
