import numpy as np
import pytest

from RAG.search import BM25, bm25_tokens, dense_top, rrf_fuse

DOCS = [
    "The brig Endeavour arrived from Lisbon carrying cork and salt.",
    "The harbour master Josiah Penrose recorded the duty on the cargo.",
    "Grain prices rose after the flood; the mill was ruined.",
    "Café owners on the quay complained about the excise.",
]


def test_tokens_are_lowercased_and_accent_folded():
    assert bm25_tokens("Café, Łódź and NAÏVE!") == ["cafe", "lodz", "and", "naive"]


def test_bm25_ranks_rare_name_matches_first():
    bm25 = BM25([bm25_tokens(d) for d in DOCS])
    # (In a 4-document corpus "was" would be as rare as the name, so avoid it.)
    assert bm25.top(bm25_tokens("What did Penrose note?"), 2)[0][0] == 1
    assert bm25.top(bm25_tokens("cafe owners"), 1)[0][0] == 3  # accent-insensitive


def test_bm25_idf_downweights_common_words():
    bm25 = BM25([bm25_tokens(d) for d in DOCS])
    scores = bm25.scores(bm25_tokens("the Lisbon"))
    assert int(np.argmax(scores)) == 0


def test_bm25_without_matches_returns_nothing():
    bm25 = BM25([bm25_tokens(d) for d in DOCS])
    assert bm25.top(bm25_tokens("zebra"), 3) == []
    assert BM25([]).top(["anything"], 3) == []


def test_bm25_length_normalisation():
    short = "penrose"
    long = "penrose " + "filler words " * 50
    bm25 = BM25([bm25_tokens(long), bm25_tokens(short)])
    assert bm25.top(["penrose"], 2)[0][0] == 1


def test_dense_top_returns_highest_cosine_first():
    m = np.eye(4, dtype=np.float32)
    q = np.array([0.1, 0.9, 0.3, 0.0], dtype=np.float32)
    assert [i for i, _ in dense_top(m, q, 3)] == [1, 2, 0]
    assert dense_top(np.zeros((0, 4), np.float32), q, 3) == []


def test_rrf_fuse_rewards_agreement():
    fused = rrf_fuse([[1, 2, 3], [2, 1, 4]], k=60)
    order = [doc for doc, _ in fused]
    assert order[:2] in ([1, 2], [2, 1]) and set(order) == {1, 2, 3, 4}
    assert dict(fused)[1] == pytest.approx(1 / 61 + 1 / 62)
    assert dict(fused)[4] == pytest.approx(1 / 63)
    assert dict(fused)[1] > dict(fused)[3]


def test_rrf_default_keeps_a_single_list_top_hit_near_the_top():
    # A passage ranked first by one search must not sink below passages that
    # both searches rank middling (k=60 let it fall out of the top 20 in eval/).
    dense = [100] + list(range(1, 30))
    lexical = list(range(30, 1, -1))   # shares 2..29 with dense, lacks 100
    order = [d for d, _ in rrf_fuse([dense, lexical])]
    assert order.index(100) < 3


def test_rrf_fuse_with_one_empty_ranking():
    assert [d for d, _ in rrf_fuse([[5, 6], []])] == [5, 6]
