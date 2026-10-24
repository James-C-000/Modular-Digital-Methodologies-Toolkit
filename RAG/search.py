"""Lexical and dense search plus rank fusion, in plain numpy.

Dense search is brute-force cosine similarity on L2-normalised embeddings: for
a humanities corpus of tens of thousands of chunks (384-dim float32: 15 MB per
10k chunks) a query takes a few milliseconds.  An approximate index (HNSW etc.)
becomes worth reintroducing only at hundreds of thousands to millions of chunks.

BM25 matters for names, dates and rare terms, which dense models often blur.
"""
import math
import unicodedata
from collections import Counter, defaultdict

import numpy as np

from NLP.text_utils import word_spans


def bm25_tokens(text: str) -> list[str]:
    """Lowercased, accent-folded word tokens ("Café" -> "cafe", "Łódź" -> "lodz")."""
    out = []
    for word, _s, _e in word_spans(text):
        folded = unicodedata.normalize("NFKD", word.lower()).replace("ł", "l")
        out.append("".join(ch for ch in folded if not unicodedata.combining(ch)))
    return out


class BM25:
    """Okapi BM25 with Lucene's non-negative IDF."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.doc_len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if self.n else 0.0
        postings = defaultdict(lambda: ([], []))
        for i, doc in enumerate(docs):
            for term, tf in Counter(doc).items():
                postings[term][0].append(i)
                postings[term][1].append(tf)
        self.postings = {t: (np.array(ids, np.int32), np.array(tfs, np.float32)) for t, (ids, tfs) in postings.items()}
        self.idf = {t: math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5))
                    for t, (ids, _tfs) in self.postings.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        scores = np.zeros(self.n, dtype=np.float32)
        if not self.n:
            return scores
        norm = self.k1 * (1 - self.b + self.b * self.doc_len / max(self.avgdl, 1e-9))
        for term in set(query):
            if term not in self.postings:
                continue
            ids, tfs = self.postings[term]
            scores[ids] += self.idf[term] * tfs * (self.k1 + 1) / (tfs + norm[ids])
        return scores

    def top(self, query: list[str], k: int) -> list[tuple[int, float]]:
        scores = self.scores(query)
        hits = np.nonzero(scores > 0)[0]
        best = hits[np.argsort(-scores[hits])[:k]]
        return [(int(i), float(scores[i])) for i in best]


# Reciprocal Rank Fusion constant.  The usual 60 let a passage ranked first by
# one search fall below passages both searches ranked middling; on eval/ a small
# k gave Recall@6 0.59 vs 0.48 without the reranker (0.72 vs 0.67 with it), and
# a leave-one-book-out choice of k picked 2-5 for every book.
RRF_K = 5


def dense_top(matrix: np.ndarray, query: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Top-k rows of an L2-normalised *matrix* by cosine similarity to *query*."""
    if matrix.shape[0] == 0:
        return []
    scores = matrix @ query
    k = min(k, len(scores))
    best = np.argpartition(-scores, k - 1)[:k]
    best = best[np.argsort(-scores[best])]
    return [(int(i), float(scores[i])) for i in best]


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: sum of 1 / (k + rank) over the rankings (rank from 1)."""
    fused = defaultdict(float)
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            fused[doc] += 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
