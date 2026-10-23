"""Named entity recognition with ONNX Runtime and Hugging Face tokenizers (no torch).

The model is an ONNX export of a BERT token-classification model, downloaded on
demand (Downloads page or first use) into ``<models>/ner/<key>/``.

Long texts are processed in overlapping windows of up to 510 word pieces; each
token keeps the prediction from the window in which it is furthest from an
edge (most context on both sides).  Token labels are then grouped into
entities the same way as the transformers pipeline's ``aggregation_strategy=
"simple"``: consecutive tokens of the same entity type form one entity, and a
``B-`` tag always starts a new one.
"""
import json
import os
import threading

import numpy as np

# Registry of downloadable NER models.  Revisions are pinned.
NER_MODELS = {
    "multilingual": {
        "name": "Multilingual NER (mBERT, 10 languages)",
        "repo_id": "Xenova/bert-base-multilingual-cased-ner-hrl",
        "revision": "263e82c06569c8c2ac46238a7ae5107598934234",
        "files": ["onnx/model_int8.onnx", "tokenizer.json", "config.json"],
        "source": "https://huggingface.co/Davlan/bert-base-multilingual-cased-ner-hrl",
        "license": "AFL-3.0",
        "size": "~182 MB",
        "languages": "Arabic, Chinese, Dutch, English, French, German, Italian, Latvian, Portuguese, Spanish",
        "labels": ["PER", "ORG", "LOC", "DATE"],
    },
}
DEFAULT_NER_MODEL = "multilingual"

WINDOW = 510      # word pieces per window (512 minus [CLS] and [SEP])
STRIDE = 382      # 128 tokens of overlap between windows


def model_dir(key: str, models_root: str) -> str:
    return os.path.join(models_root, "ner", key)


def is_model_installed(key: str = DEFAULT_NER_MODEL, models_root: str | None = None) -> bool:
    from common.hf_models import is_snapshot_complete
    return is_snapshot_complete(model_dir(key, models_root or _default_root()), NER_MODELS[key]["files"])


def download_model(key: str = DEFAULT_NER_MODEL, models_root: str | None = None) -> str:
    from common.hf_models import download_snapshot
    info = NER_MODELS[key]
    return download_snapshot(info["repo_id"], info["revision"], info["files"],
                             model_dir(key, models_root or _default_root()))


def _default_root() -> str:
    from config import get_models_dir
    return get_models_dir()


# ------------------------------------------------------------- windows ----

def window_starts(n_tokens: int, size: int = WINDOW, stride: int = STRIDE) -> list[int]:
    """Start offsets of overlapping windows covering *n_tokens* tokens."""
    if n_tokens <= size:
        return [0]
    starts = list(range(0, n_tokens - size, stride))
    starts.append(n_tokens - size)
    return starts


def best_window_for_tokens(n_tokens: int, starts: list[int], size: int = WINDOW) -> list[int]:
    """For each token, the window start where the token is furthest from an edge."""
    best, best_margin = [0] * n_tokens, [-1] * n_tokens
    for start in starts:
        for i in range(start, min(start + size, n_tokens)):
            margin = min(i - start, start + size - 1 - i)
            if margin > best_margin[i]:
                best[i], best_margin[i] = start, margin
    return best


# --------------------------------------------------------- aggregation ----

def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def aggregate_simple(text: str, offsets, logits: np.ndarray, labels: list[str]) -> list[dict]:
    """Group per-token predictions into entities (pipeline "simple" strategy).

    offsets: (start, end) character span of each token; logits: (tokens, labels).
    Returns dicts with entity_group, score, word, start, end.
    """
    probs = _softmax(logits)
    ids = probs.argmax(-1)
    entities, current = [], None
    for (start, end), label_id, p in zip(offsets, ids, probs):
        label = labels[label_id]
        if label == "O" or start == end:
            current = None
            continue
        prefix, _, kind = label.partition("-") if "-" in label else ("I", "", label)
        if current is not None and prefix != "B" and kind == current["entity_group"]:
            current["end"] = end
            current["_scores"].append(float(p[label_id]))
        else:
            current = {"entity_group": kind, "start": start, "end": end, "_scores": [float(p[label_id])]}
            entities.append(current)
    for e in entities:
        scores = e.pop("_scores")
        e["score"] = float(np.mean(scores))
        e["word"] = text[e["start"]:e["end"]]
    return entities


# --------------------------------------------------------------- model ----

class NerModel:
    def __init__(self, path: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        with open(os.path.join(path, "config.json"), encoding="utf-8") as f:
            config = json.load(f)
        self.labels = [config["id2label"][str(i)] for i in range(len(config["id2label"]))]
        self.tokenizer = Tokenizer.from_file(os.path.join(path, "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.cls_id = self.tokenizer.token_to_id("[CLS]")
        self.sep_id = self.tokenizer.token_to_id("[SEP]")
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            os.path.join(path, "onnx", "model_int8.onnx"), options, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self._lock = threading.Lock()

    def _run(self, ids: list[int]) -> np.ndarray:
        ids = [self.cls_id] + ids + [self.sep_id]
        feeds = {"input_ids": np.array([ids], dtype=np.int64),
                 "attention_mask": np.ones((1, len(ids)), dtype=np.int64)}
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros((1, len(ids)), dtype=np.int64)
        with self._lock:
            logits = self.session.run(None, feeds)[0][0]
        return logits[1:-1]  # drop [CLS]/[SEP]

    def predict(self, text: str) -> list[dict]:
        """Entities in *text* with character offsets into *text*."""
        if not text.strip():
            return []
        enc = self.tokenizer.encode(text, add_special_tokens=False)
        n = len(enc.ids)
        if n == 0:
            return []
        starts = window_starts(n)
        window_logits = {s: self._run(enc.ids[s:s + WINDOW]) for s in starts}
        best = best_window_for_tokens(n, starts)
        logits = np.stack([window_logits[best[i]][i - best[i]] for i in range(n)])
        return aggregate_simple(text, enc.offsets, logits, self.labels)


_loaded: dict[str, NerModel] = {}
_load_lock = threading.Lock()


def load_model(key: str = DEFAULT_NER_MODEL, models_root: str | None = None) -> NerModel:
    """Load (downloading if necessary) and cache an NER model."""
    root = models_root or _default_root()
    cache_key = f"{key}@{root}"
    with _load_lock:
        if cache_key not in _loaded:
            _loaded[cache_key] = NerModel(download_model(key, root))
        return _loaded[cache_key]
