"""Benchmark embedding/reranking runtimes for the Phase 3 RAG design (dev-only).

Compares llama.cpp (the JamePeng fork's LlamaEmbedding, GGUF) with ONNX Runtime
+ tokenizers on the same models, and records speed, memory and how closely the
two runtimes agree.

    python tests/dev/bench_retrieval_runtimes.py --out results.json [--threads 4] [--models-dir DIR]

Downloads ~3 GB of models on first run.
"""
import argparse
import gc
import json
import os
import platform
import statistics
import sys
import time

import numpy as np
import psutil
from huggingface_hub import hf_hub_download

PASSAGE = (
    "The parish register of St Mary's records that on the fourteenth of March 1743 the miller "
    "John Harrow brought his second son to be baptised, and that the godparents were Thomas "
    "Webb, a carter from the neighbouring village, and Ann Lowe, the widow of the former "
    "schoolmaster. A later hand has added in the margin that the boy died of smallpox in the "
    "winter of 1751, the same winter in which the mill was flooded and the bridge carried away."
)
TOPICS = ["baptism", "harvest", "flood", "trade", "court", "school", "letters", "war", "church", "market"]
PASSAGES = [f"[{i}] ({TOPICS[i % len(TOPICS)]}) " + PASSAGE for i in range(64)]
QUERY = "When was the miller's son baptised and who were the godparents?"
RERANK_DOCS = [PASSAGE] + [f"A note about the {t} in the parish accounts for the year 17{40 + i}." for i, t in
                           enumerate(TOPICS * 3)][:24]

EMBEDDERS = {
    "qwen3-embedding-0.6b": {
        "gguf": ("Qwen/Qwen3-Embedding-0.6B-GGUF", "Qwen3-Embedding-0.6B-Q8_0.gguf"),
        "onnx": ("onnx-community/Qwen3-Embedding-0.6B-ONNX", "onnx/model_uint8.onnx", "last"),
        "query_prefix": "Instruct: Given a question, retrieve passages that answer it\nQuery: ",
        "passage_prefix": "",
    },
    "multilingual-e5-small": {
        "onnx": ("Xenova/multilingual-e5-small", "onnx/model_uint8.onnx", "mean"),
        "onnx_reference": ("Xenova/multilingual-e5-small", "onnx/model.onnx", "mean"),  # fp32
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "bge-m3": {
        "gguf": ("ggml-org/bge-m3-Q8_0-GGUF", "bge-m3-q8_0.gguf"),
        "query_prefix": "",
        "passage_prefix": "",
    },
}
RERANKERS = {
    "bge-reranker-v2-m3": {
        "gguf": ("gpustack/bge-reranker-v2-m3-GGUF", "bge-reranker-v2-m3-Q8_0.gguf"),
        "onnx": ("onnx-community/bge-reranker-v2-m3-ONNX", "onnx/model_uint8.onnx"),
    },
}


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 2**20


def timed(fn, repeat=3):
    times = []
    out = None
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t)
    return out, statistics.median(times)


# ------------------------------------------------------------------ ONNX ----

class OnnxEncoder:
    def __init__(self, repo, file, threads, pooling=None, pair=False):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json"))
        self.tok.enable_truncation(512)
        path = hf_hub_download(repo, file)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
        self.inputs = [i.name for i in self.sess.get_inputs()]
        outputs = [o.name for o in self.sess.get_outputs()]
        self.hidden_output = "last_hidden_state" if "last_hidden_state" in outputs else outputs[0]
        self.pooling, self.pair = pooling, pair

    def _feeds(self, encs):
        n = max(len(e.ids) for e in encs)
        left = self.pooling == "last"  # decoder models: pad on the left
        ids = np.zeros((len(encs), n), np.int64)
        mask = np.zeros((len(encs), n), np.int64)
        for i, e in enumerate(encs):
            sl = slice(n - len(e.ids), n) if left else slice(0, len(e.ids))
            ids[i, sl], mask[i, sl] = e.ids, 1
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feeds["token_type_ids"] = np.zeros_like(ids)
        if "position_ids" in self.inputs:
            feeds["position_ids"] = np.clip(np.cumsum(mask, axis=1) - 1, 0, None)
        # Decoder exports (Qwen3) also take a key/value cache: pass it empty.
        for meta in self.sess.get_inputs():
            if meta.name.startswith("past_key_values"):
                _b, heads, _len, dim = meta.shape
                dtype = np.float16 if "float16" in meta.type else np.float32
                feeds[meta.name] = np.zeros((len(encs), heads, 0, dim), dtype)
        return {k: v for k, v in feeds.items() if k in self.inputs}, mask

    def embed(self, texts, batch=16):
        out = []
        for i in range(0, len(texts), batch):
            feeds, mask = self._feeds(self.tok.encode_batch(texts[i:i + batch]))
            hidden = self.sess.run([self.hidden_output], feeds)[0].astype(np.float32)
            if self.pooling == "last":
                vec = hidden[:, -1]
            else:
                m = mask[..., None]
                vec = (hidden * m).sum(1) / m.sum(1)
            out.append(vec / np.linalg.norm(vec, axis=1, keepdims=True))
        return np.concatenate(out)

    def rank(self, query, docs):
        feeds, _ = self._feeds(self.tok.encode_batch([(query, d) for d in docs]))
        return self.sess.run(None, feeds)[0][:, 0]


# ------------------------------------------------------------- llama.cpp ----

class LlamaEncoder:
    def __init__(self, repo, file, threads, rank=False):
        from llama_cpp import LLAMA_POOLING_TYPE_RANK, LLAMA_POOLING_TYPE_UNSPECIFIED
        from llama_cpp.llama_embedding import LlamaEmbedding
        gpu = -1 if sys.platform == "darwin" else 0  # Metal on Apple Silicon
        self.llm = LlamaEmbedding(
            model_path=hf_hub_download(repo, file), n_ctx=8192, n_batch=2048, n_ubatch=512,
            n_threads=threads, n_gpu_layers=gpu, verbose=False,
            pooling_type=LLAMA_POOLING_TYPE_RANK if rank else LLAMA_POOLING_TYPE_UNSPECIFIED)

    def embed(self, texts):
        return np.array(self.llm.embed(texts))

    def rank(self, query, docs):
        return np.array(self.llm.rank(query, docs))


# ------------------------------------------------------------------ main ----

def _prefetch(spec):
    hf_hub_download(spec[0], spec[1])
    if spec[1].endswith(".onnx"):
        hf_hub_download(spec[0], "tokenizer.json")


def bench_embedder(name, cfg, runtime, threads):
    r = {"model": name, "runtime": runtime}
    _prefetch(cfg[runtime])  # downloads are not part of the load time
    gc.collect()
    before = rss_mb()
    t = time.perf_counter()
    if runtime == "onnx":
        repo, file, pooling = cfg["onnx"]
        enc = OnnxEncoder(repo, file, threads, pooling)
    else:
        enc = LlamaEncoder(*cfg["gguf"], threads)
    r["load_s"] = round(time.perf_counter() - t, 2)
    passages = [cfg["passage_prefix"] + p for p in PASSAGES]
    enc.embed(passages[:4])  # warm-up
    vecs, dt = timed(lambda: enc.embed(passages), repeat=2)
    r["passages_per_s"] = round(len(passages) / dt, 1)
    q, dq = timed(lambda: enc.embed([cfg["query_prefix"] + QUERY]), repeat=5)
    r["query_ms"] = round(dq * 1000, 1)
    r["rss_mb"] = round(rss_mb() - before)
    r["dim"] = int(vecs.shape[1])
    del enc
    gc.collect()
    return r, vecs, q


def bench_reranker(name, cfg, runtime, threads):
    r = {"model": name, "runtime": runtime}
    _prefetch(cfg[runtime])
    gc.collect()
    before = rss_mb()
    t = time.perf_counter()
    enc = OnnxEncoder(*cfg["onnx"], threads, pair=True) if runtime == "onnx" else \
        LlamaEncoder(*cfg["gguf"], threads, rank=True)
    r["load_s"] = round(time.perf_counter() - t, 2)
    enc.rank(QUERY, RERANK_DOCS[:2])
    scores, dt = timed(lambda: enc.rank(QUERY, RERANK_DOCS), repeat=3)
    r["rerank_25_ms"] = round(dt * 1000, 1)
    r["rss_mb"] = round(rss_mb() - before)
    r["top1_is_relevant"] = bool(int(np.argmax(scores)) == 0)
    del enc
    gc.collect()
    return r, scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    import llama_cpp
    info = {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version.split()[0],
            "cpu_count": os.cpu_count(), "threads": args.threads,
            "llama_cpp": llama_cpp.__version__,
            "llama_system_info": llama_cpp.llama_print_system_info().decode()}
    results = {"info": info, "embedders": [], "rerankers": [], "agreement": {}}

    for name, cfg in EMBEDDERS.items():
        outs = {}
        for runtime in ("gguf", "onnx"):
            if runtime in cfg:
                r, vecs, q = bench_embedder(name, cfg, runtime, args.threads)
                results["embedders"].append(r)
                outs[runtime] = (vecs, q)
                print(json.dumps(r), flush=True)
        def mean_cos(a, b):
            return round(float(np.mean(np.sum(a * b, axis=1) /
                                       (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)))), 4)
        if len(outs) == 2:
            results["agreement"][name] = {"mean_cosine_gguf_vs_onnx": mean_cos(outs["gguf"][0], outs["onnx"][0])}
        if "onnx_reference" in cfg:
            _prefetch(cfg["onnx_reference"])
            ref = OnnxEncoder(*cfg["onnx_reference"][:2], args.threads, cfg["onnx_reference"][2])
            ref_vecs = ref.embed([cfg["passage_prefix"] + p for p in PASSAGES])
            results["agreement"][name] = {"mean_cosine_uint8_vs_fp32": mean_cos(outs["onnx"][0], ref_vecs)}
            del ref
            gc.collect()

    for name, cfg in RERANKERS.items():
        outs = {}
        for runtime in ("gguf", "onnx"):
            r, scores = bench_reranker(name, cfg, runtime, args.threads)
            results["rerankers"].append(r)
            outs[runtime] = scores
            print(json.dumps(r), flush=True)
        a, b = outs["gguf"], outs["onnx"]
        top5 = len(set(np.argsort(-a)[:5]) & set(np.argsort(-b)[:5])) / 5
        results["agreement"][name] = {"score_correlation": round(float(np.corrcoef(a, b)[0, 1]), 4),
                                      "top5_overlap": top5}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(json.dumps(results["agreement"]))


if __name__ == "__main__":
    main()
