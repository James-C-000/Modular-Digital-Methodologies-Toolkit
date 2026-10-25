"""Persistent, incremental RAG index for one document folder.

Stored under ``config.get_index_dir()/<key>/`` where the key hashes the corpus
path, the embedding model and the chunking parameters, so changing any of them
starts a separate index.  Files:

- ``manifest.json``: per document: size, mtime, SHA-256 and its chunk range;
- ``chunks.json``: chunk text and metadata (file, page, character offsets);
- ``embeddings.npy``: float32 matrix, one L2-normalised row per chunk.

``update()`` re-chunks and re-embeds only documents that are new or whose
content changed (a size/mtime change triggers a hash check, so a merely
touched file is not re-embedded), and drops removed documents.  Files are
replaced atomically, the manifest last; on load, an index whose manifest does
not describe its chunks (a crash between the two) is rebuilt.  BM25 is rebuilt
in memory on load.  Searches see the index before or after an update, never
half of each.
"""
import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass, field

import numpy as np

from RAG.chunking import MAX_TOKENS, OVERLAP_TOKENS, Chunk, chunk_document
from RAG.loaders import find_documents, load_document
from RAG.search import BM25, bm25_tokens, dense_top, rrf_fuse

FORMAT_VERSION = 1


@dataclass
class UpdateReport:
    added: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    unchanged: int = 0
    failed: list = field(default_factory=list)   # (relative path, error message)
    chunks: int = 0


@dataclass
class Hit:
    chunk: Chunk
    index: int               # row in the index
    fused_score: float
    dense_rank: int | None   # 1-based rank in each list, None if absent
    bm25_rank: int | None
    rerank_score: float | None = None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_matches(manifest: dict, chunks: list) -> bool:
    """True if every file's chunk range in *manifest* holds that file's chunks, and nothing else is there."""
    covered = 0
    try:
        for rel, info in manifest.get("files", {}).items():
            start, count = info["chunks"]
            if start < 0 or start + count > len(chunks) or any(c.file != rel for c in chunks[start:start + count]):
                return False
            covered += count
    except (KeyError, TypeError, ValueError):
        return False
    return covered == len(chunks)


def _atomic_write(path: str, write):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        write(f)
    os.replace(tmp, path)


class CorpusIndex:
    def __init__(self, corpus_dir: str, embedder, index_root: str | None = None,
                 max_tokens: int = MAX_TOKENS, overlap_tokens: int = OVERLAP_TOKENS):
        if index_root is None:
            from config import get_index_dir
            index_root = get_index_dir()
        self.corpus_dir = os.path.realpath(corpus_dir)
        self.embedder = embedder
        self.max_tokens, self.overlap_tokens = max_tokens, overlap_tokens
        key_source = json.dumps([self.corpus_dir, embedder.model_id, max_tokens, overlap_tokens, FORMAT_VERSION])
        self.path = os.path.join(index_root, hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:16])
        self.manifest = {"files": {}}
        self.chunks: list[Chunk] = []
        self.embeddings = np.zeros((0, embedder.dim), np.float32)
        self._bm25 = None             # (the chunks it was built from, BM25)
        self._lock = threading.Lock()  # chunks and embeddings change together
        self._load()

    # ------------------------------------------------------------ storage ----

    def _load(self):
        try:
            with open(os.path.join(self.path, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            with open(os.path.join(self.path, "chunks.json"), encoding="utf-8") as f:
                chunks = [Chunk(**c) for c in json.load(f)]
            embeddings = np.load(os.path.join(self.path, "embeddings.npy"))
        except (OSError, ValueError, TypeError):
            return  # no index yet, or unreadable: rebuilt by update()
        if (manifest.get("format") == FORMAT_VERSION and len(chunks) == embeddings.shape[0]
                and _manifest_matches(manifest, chunks)):
            self.manifest, self.chunks, self.embeddings = manifest, chunks, embeddings.astype(np.float32)
            self._bm25 = None

    def _save(self):
        os.makedirs(self.path, exist_ok=True)
        _atomic_write(os.path.join(self.path, "embeddings.npy"), lambda f: np.save(f, self.embeddings))
        _atomic_write(os.path.join(self.path, "chunks.json"),
                      lambda f: f.write(json.dumps([asdict(c) for c in self.chunks], ensure_ascii=False).encode("utf-8")))
        manifest = dict(self.manifest, format=FORMAT_VERSION, corpus=self.corpus_dir,
                        model=self.embedder.model_id,
                        params={"max_tokens": self.max_tokens, "overlap_tokens": self.overlap_tokens})
        _atomic_write(os.path.join(self.path, "manifest.json"),
                      lambda f: f.write(json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")))
        self.manifest = manifest

    # ------------------------------------------------------------- update ----

    def update(self, on_progress=None) -> UpdateReport:
        """Bring the index in line with the folder; returns what changed.

        Raises FileNotFoundError if the folder is gone (an unplugged drive, say)
        rather than emptying the index.
        """
        if not os.path.isdir(self.corpus_dir):
            raise FileNotFoundError(f"The documents folder was not found: {self.corpus_dir}")
        report = UpdateReport()
        old_files = self.manifest.get("files", {})
        unreadable = []
        current = {os.path.relpath(p, self.corpus_dir).replace(os.sep, "/"): p
                   for p in find_documents(self.corpus_dir, unreadable)}
        report.failed += [(os.path.relpath(folder, self.corpus_dir).replace(os.sep, "/"),
                           f"folder could not be opened ({why})") for folder, why in unreadable]

        keep, todo = {}, []
        for rel, path in current.items():
            old = old_files.get(rel)
            try:
                st = os.stat(path)
                if old and old["size"] == st.st_size and old["mtime_ns"] == st.st_mtime_ns:
                    keep[rel] = old
                    continue
                if old and old["size"] == st.st_size and old["sha256"] == _sha256(path):
                    keep[rel] = dict(old, mtime_ns=st.st_mtime_ns)  # touched, same content
                    continue
            except OSError as e:   # a broken link, or no permission to read it
                report.failed.append((rel, e.strerror or str(e)))
                continue
            todo.append(rel)
            (report.changed if old else report.added).append(rel)
        report.removed = sorted(set(old_files) - set(current))
        report.unchanged = len(keep)

        # Rows of documents we keep, in their existing order.
        rows, new_chunks, new_files = [], [], {}
        for rel, info in keep.items():
            start, count = info["chunks"]
            rows.extend(range(start, start + count))
        kept_chunks = [self.chunks[i] for i in rows]
        kept_vectors = self.embeddings[rows] if rows else np.zeros((0, self.embedder.dim), np.float32)

        total = len(current)
        done = len(keep)
        if on_progress:
            on_progress(done, total, "")
        fresh_chunks, fresh_vectors = [], []
        for rel in todo:
            path = current[rel]
            if on_progress:
                on_progress(done, total, rel)
            try:
                # Taken before reading: a file saved again while it is indexed then
                # no longer matches, so the next update reads it again.
                st = os.stat(path)
                info = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": _sha256(path)}
                chunks = chunk_document(rel, load_document(path), self.embedder.count_tokens,
                                        self.max_tokens, self.overlap_tokens)
                vectors = self.embedder.embed_passages([c.text for c in chunks])
            except Exception as e:
                report.failed.append((rel, str(e)))
                if rel in report.added:
                    report.added.remove(rel)
                if rel in report.changed:
                    report.changed.remove(rel)
                done += 1
                continue
            new_files[rel] = dict(info, chunks=[0, len(chunks)])
            fresh_chunks.append(chunks)
            fresh_vectors.append(vectors)
            done += 1
        if on_progress:
            on_progress(total, total, "")

        # Reassemble: kept documents first, then new ones; recompute ranges.
        files, offset = {}, 0
        for rel, info in keep.items():
            files[rel] = dict(info, chunks=[offset, info["chunks"][1]])
            offset += info["chunks"][1]
        new_chunks = list(kept_chunks)
        for (rel, info), chunks in zip(new_files.items(), fresh_chunks):
            files[rel] = dict(info, chunks=[offset, len(chunks)])
            offset += len(chunks)
            new_chunks.extend(chunks)
        vectors = [kept_vectors] + [v for v in fresh_vectors if len(v)]
        embeddings = np.concatenate(vectors).astype(np.float32) if vectors else kept_vectors
        with self._lock:
            self.embeddings, self.chunks = embeddings, new_chunks
            self.manifest = {"files": files}
            self._bm25 = None
        report.chunks = len(new_chunks)
        self._save()
        return report

    # ------------------------------------------------------------- search ----

    def _bm25_for(self, chunks: list) -> BM25:
        """BM25 over *chunks*, built once per version of the index."""
        cached = self._bm25
        if cached is not None and cached[0] is chunks:
            return cached[1]
        bm25 = BM25([bm25_tokens(c.text) for c in chunks])
        with self._lock:
            if self.chunks is chunks:   # not if an update replaced them meanwhile
                self._bm25 = (chunks, bm25)
        return bm25

    @property
    def bm25(self) -> BM25:
        return self._bm25_for(self.chunks)

    def search(self, query: str, k: int = 25, k_dense: int = 50, k_bm25: int = 50) -> list[Hit]:
        """Hybrid retrieval: dense + BM25 fused with Reciprocal Rank Fusion."""
        with self._lock:
            chunks, embeddings = self.chunks, self.embeddings
        if not chunks:
            return []
        dense = [i for i, _s in dense_top(embeddings, self.embedder.embed_query(query), k_dense)]
        lexical = [i for i, _s in self._bm25_for(chunks).top(bm25_tokens(query), k_bm25)]
        dense_rank = {doc: r for r, doc in enumerate(dense, 1)}
        bm25_rank = {doc: r for r, doc in enumerate(lexical, 1)}
        return [Hit(chunks[i], i, score, dense_rank.get(i), bm25_rank.get(i))
                for i, score in rrf_fuse([dense, lexical])[:k]]
