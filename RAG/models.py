"""Embedding and reranking models for RAG, run with ONNX Runtime + tokenizers.

Chosen in the Phase 3 design (benchmarks: tests/dev/bench_retrieval_runtimes.py):

- Embedder: intfloat/multilingual-e5-small (MIT; 94 languages; 384-dim;
  512 tokens).  ~25-40 chunks/s on a 4-core laptop CPU.
- Reranker: BAAI/bge-reranker-v2-m3 (Apache-2.0; multilingual cross-encoder).

Both use uint8-weight (U8U8) ONNX exports: int8-weight exports can saturate on
x86 CPUs without AVX-512 VNNI (see NLP/ner_onnx.py).  Revisions are pinned and
files are downloaded on demand into ``<models>/rag/<key>/``.
"""
import json
import os
import threading

import numpy as np

EMBEDDER = {
    "key": "multilingual-e5-small",
    "name": "Multilingual E5 small (embeddings)",
    "repo_id": "Xenova/multilingual-e5-small",
    "revision": "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
    "files": ["onnx/model_uint8.onnx", "tokenizer.json", "config.json"],
    "source": "https://huggingface.co/intfloat/multilingual-e5-small",
    "license": "MIT",
    "size": "~135 MB",
    "max_tokens": 512,
    "query_prefix": "query: ",
    "passage_prefix": "passage: ",
}
RERANKER = {
    "key": "bge-reranker-v2-m3",
    "name": "BGE reranker v2 m3 (reranking)",
    "repo_id": "onnx-community/bge-reranker-v2-m3-ONNX",
    "revision": "6f5ff65298512715a1e669753bc754d2bc8f367b",
    "files": ["onnx/model_uint8.onnx", "tokenizer.json", "config.json"],
    "source": "https://huggingface.co/BAAI/bge-reranker-v2-m3",
    "license": "Apache-2.0",
    "size": "~588 MB",
    "max_tokens": 512,
}
RAG_MODELS = {EMBEDDER["key"]: EMBEDDER, RERANKER["key"]: RERANKER}


def models_root() -> str:
    from config import get_models_dir
    return os.path.join(get_models_dir(), "rag")


def model_dir(info: dict, root: str | None = None) -> str:
    return os.path.join(root or models_root(), info["key"])


def is_installed(info: dict, root: str | None = None) -> bool:
    from common.hf_models import is_snapshot_complete
    return is_snapshot_complete(model_dir(info, root), info["files"])


def download(info: dict, root: str | None = None) -> str:
    from common.hf_models import download_snapshot
    return download_snapshot(info["repo_id"], info["revision"], info["files"], model_dir(info, root))


def _session(path: str, threads: int | None):
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.log_severity_level = 3
    if threads:
        options.intra_op_num_threads = threads
    return ort.InferenceSession(path, options, providers=["CPUExecutionProvider"])


def _pad(encodings, pair_types=False):
    n = max(len(e.ids) for e in encodings)
    ids = np.zeros((len(encodings), n), np.int64)
    mask = np.zeros((len(encodings), n), np.int64)
    types = np.zeros((len(encodings), n), np.int64)
    for i, e in enumerate(encodings):
        ids[i, :len(e.ids)] = e.ids
        mask[i, :len(e.ids)] = 1
        if pair_types:
            types[i, :len(e.ids)] = e.type_ids
    return ids, mask, types


class Embedder:
    """Sentence embeddings (mean pooling, L2-normalised)."""

    def __init__(self, root: str | None = None, threads: int | None = None):
        from tokenizers import Tokenizer
        path = download(EMBEDDER, root)
        self.tokenizer = Tokenizer.from_file(os.path.join(path, "tokenizer.json"))
        self.tokenizer.no_padding()
        self.tokenizer.enable_truncation(EMBEDDER["max_tokens"])
        self.session = _session(os.path.join(path, "onnx", "model_uint8.onnx"), threads)
        self.inputs = {i.name for i in self.session.get_inputs()}
        with open(os.path.join(path, "config.json"), encoding="utf-8") as f:
            self.dim = json.load(f).get("hidden_size", 384)
        self._lock = threading.Lock()
        self.model_id = f"{EMBEDDER['repo_id']}@{EMBEDDER['revision'][:12]}"

    def count_tokens(self, text: str) -> int:
        """Word pieces in *text* (without special tokens or the prefix)."""
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def _encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        out = []
        # Sort by length so batches pad little; restore the order afterwards.
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            ids, mask, types = _pad(self.tokenizer.encode_batch([texts[i] for i in idx]))
            feeds = {"input_ids": ids, "attention_mask": mask, "token_type_ids": types}
            with self._lock:
                hidden = self.session.run(None, {k: v for k, v in feeds.items() if k in self.inputs})[0]
            m = mask[..., None].astype(np.float32)
            vecs = (hidden * m).sum(1) / np.maximum(m.sum(1), 1e-9)
            vecs /= np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
            out.extend(zip(idx, vecs))
        out.sort(key=lambda pair: pair[0])
        return np.stack([v for _i, v in out]).astype(np.float32) if out else np.zeros((0, self.dim), np.float32)

    def embed_passages(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        return self._encode([EMBEDDER["passage_prefix"] + t for t in texts], batch_size)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([EMBEDDER["query_prefix"] + text])[0]


class Reranker:
    """Cross-encoder relevance scores for (query, passage) pairs."""

    def __init__(self, root: str | None = None, threads: int | None = None):
        from tokenizers import Tokenizer
        path = download(RERANKER, root)
        self.tokenizer = Tokenizer.from_file(os.path.join(path, "tokenizer.json"))
        self.tokenizer.no_padding()
        self.tokenizer.enable_truncation(RERANKER["max_tokens"], strategy="only_second")
        self.session = _session(os.path.join(path, "onnx", "model_uint8.onnx"), threads)
        self.inputs = {i.name for i in self.session.get_inputs()}
        self._lock = threading.Lock()

    def score(self, query: str, passages: list[str], batch_size: int = 8) -> np.ndarray:
        """Higher is more relevant (raw logits)."""
        scores = []
        for start in range(0, len(passages), batch_size):
            batch = passages[start:start + batch_size]
            ids, mask, types = _pad(self.tokenizer.encode_batch([(query, p) for p in batch]), pair_types=True)
            feeds = {"input_ids": ids, "attention_mask": mask, "token_type_ids": types}
            with self._lock:
                logits = self.session.run(None, {k: v for k, v in feeds.items() if k in self.inputs})[0]
            scores.extend(np.asarray(logits).reshape(len(batch), -1)[:, 0].tolist())
        return np.array(scores, dtype=np.float32)


_cache: dict = {}
_cache_lock = threading.Lock()


def get_embedder(root: str | None = None) -> Embedder:
    with _cache_lock:
        key = ("embedder", root)
        if key not in _cache:
            _cache[key] = Embedder(root)
        return _cache[key]


def get_reranker(root: str | None = None) -> Reranker:
    with _cache_lock:
        key = ("reranker", root)
        if key not in _cache:
            _cache[key] = Reranker(root)
        return _cache[key]
