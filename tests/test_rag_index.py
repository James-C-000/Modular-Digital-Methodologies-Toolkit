import os
import time

import numpy as np
import pytest

from RAG.index import CorpusIndex


class FakeEmbedder:
    """Deterministic bag-of-letters vectors; counts how much work it did."""
    model_id = "fake-embedder@1"
    dim = 26

    def __init__(self):
        self.embedded = 0

    def count_tokens(self, text):
        return len(text.split())

    def _vec(self, text):
        v = np.zeros(self.dim, np.float32)
        for ch in text.lower():
            if "a" <= ch <= "z":
                v[ord(ch) - 97] += 1
        return v / max(np.linalg.norm(v), 1e-9)

    def embed_passages(self, texts, batch_size=16):
        self.embedded += len(texts)
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture
def corpus(tmp_path):
    d = tmp_path / "corpus"
    d.mkdir()
    (d / "ships.txt").write_text("The brig Endeavour arrived from Lisbon. It carried cork.", encoding="utf-8")
    (d / "mill.txt").write_text("The mill flooded in 1751. Grain prices rose.", encoding="utf-8")
    return d


def _index(corpus, tmp_path, emb, **kw):
    return CorpusIndex(str(corpus), emb, index_root=str(tmp_path / "index"), **kw)


def test_first_build_indexes_everything(corpus, tmp_path):
    emb = FakeEmbedder()
    idx = _index(corpus, tmp_path, emb)
    report = idx.update()
    assert sorted(report.added) == ["mill.txt", "ships.txt"] and report.chunks == 2
    assert emb.embedded == 2
    assert {c.file for c in idx.chunks} == {"mill.txt", "ships.txt"}
    assert idx.embeddings.shape == (2, 26)


def test_reopening_reuses_the_saved_index(corpus, tmp_path):
    _index(corpus, tmp_path, FakeEmbedder()).update()
    emb = FakeEmbedder()
    idx = _index(corpus, tmp_path, emb)
    report = idx.update()
    assert report.unchanged == 2 and not report.added and emb.embedded == 0
    assert len(idx.chunks) == 2


def test_only_changed_and_new_files_are_reembedded_and_removed_files_dropped(corpus, tmp_path):
    _index(corpus, tmp_path, FakeEmbedder()).update()
    time.sleep(0.01)
    (corpus / "mill.txt").write_text("The mill was rebuilt in 1760 by the parish.", encoding="utf-8")
    (corpus / "court.txt").write_text("The court fined the miller.", encoding="utf-8")
    os.remove(corpus / "ships.txt")
    emb = FakeEmbedder()
    idx = _index(corpus, tmp_path, emb)
    report = idx.update()
    assert report.changed == ["mill.txt"] and report.added == ["court.txt"] and report.removed == ["ships.txt"]
    assert emb.embedded == 2
    assert sorted(c.file for c in idx.chunks) == ["court.txt", "mill.txt"]
    assert any("rebuilt" in c.text for c in idx.chunks)
    assert idx.embeddings.shape[0] == len(idx.chunks)


def test_touched_but_identical_file_is_not_reembedded(corpus, tmp_path):
    _index(corpus, tmp_path, FakeEmbedder()).update()
    later = time.time() + 5
    os.utime(corpus / "mill.txt", (later, later))
    emb = FakeEmbedder()
    report = _index(corpus, tmp_path, emb).update()
    assert report.unchanged == 2 and emb.embedded == 0


def test_different_model_or_chunk_settings_use_a_separate_index(corpus, tmp_path):
    a = _index(corpus, tmp_path, FakeEmbedder())
    b = _index(corpus, tmp_path, FakeEmbedder(), max_tokens=128)
    other = FakeEmbedder()
    other.model_id = "another-model@2"
    c = _index(corpus, tmp_path, other)
    assert len({a.path, b.path, c.path}) == 3


def test_unreadable_files_are_reported_not_fatal(corpus, tmp_path):
    (corpus / "broken.docx").write_bytes(b"not a zip")
    report = _index(corpus, tmp_path, FakeEmbedder()).update()
    assert [f for f, _err in report.failed] == ["broken.docx"]
    assert sorted(report.added) == ["mill.txt", "ships.txt"]


def test_hybrid_search_finds_by_name_and_by_meaning(corpus, tmp_path):
    idx = _index(corpus, tmp_path, FakeEmbedder())
    idx.update()
    hits = idx.search("Endeavour Lisbon", k=2)
    assert hits[0].chunk.file == "ships.txt"
    assert hits[0].bm25_rank == 1


def test_progress_callback(corpus, tmp_path):
    seen = []
    _index(corpus, tmp_path, FakeEmbedder()).update(on_progress=lambda done, total, name: seen.append((done, total)))
    assert seen[-1][0] == seen[-1][1] == 2
