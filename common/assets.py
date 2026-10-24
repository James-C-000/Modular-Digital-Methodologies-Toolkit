"""Everything MDMT can download, as one list for the Downloads and Welcome pages.

Built from the feature registries (Tesseract languages, Whisper models,
Argos translation packages, the NER model, the retrieval models and the Qwen
chat models); nothing here duplicates their data.  Downloads are never bundled
and always fetched on demand.
"""
import os
import re
import shutil
from dataclasses import dataclass, field

TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"
BUNDLED_TESSDATA = {"eng", "osd"}     # shipped with MDMT and re-seeded at startup


@dataclass
class Asset:
    key: str                     # unique, e.g. "whisper:small"
    section: str
    name: str
    size: int | None             # download size in bytes, if known
    note: str = ""
    bundled: bool = False
    installed_fn: object = None
    download_fn: object = None   # download_fn(on_progress) with on_progress(done_bytes, total_bytes)
    paths_fn: object = None      # what Delete removes and what counts as disk usage
    in_use_fn: object = None     # returns a reason it cannot be deleted now, or None
    license_path_fn: object = None   # the installed asset's own license/README file, if it has one

    def license_path(self) -> str | None:
        path = self.license_path_fn() if self.license_path_fn else None
        return path if path and os.path.isfile(path) else None

    def installed(self) -> bool:
        return bool(self.installed_fn())

    def download(self, on_progress=None):
        return self.download_fn(on_progress)

    def paths(self) -> list[str]:
        return [p for p in self.paths_fn() if os.path.exists(p)]

    def disk_bytes(self) -> int:
        return sum(_bytes(p) for p in self.paths())

    def delete(self):
        if self.bundled:
            raise RuntimeError(f"{self.name} ships with MDMT and cannot be removed.")
        reason = self.in_use_fn() if self.in_use_fn else None
        if reason:
            raise RuntimeError(reason)
        for path in self.paths():
            try:
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            except OSError as e:
                raise RuntimeError(f"Could not delete {path}: {e.strerror or e}. If MDMT is using it,"
                                   " restart MDMT and try again.") from e


@dataclass
class Section:
    id: str
    title: str
    note: str
    location: str
    assets: list = field(default_factory=list)


def human_bytes(n) -> str:
    """Decimal units, as model hosts state sizes."""
    if n is None:
        return "?"
    for unit, scale in (("GB", 10**9), ("MB", 10**6), ("KB", 10**3)):
        if n >= scale:
            value = n / scale
            return f"{value:.2f} {unit}" if unit == "GB" else f"{value:.0f} {unit}"
    return f"{n} B"


def _parse_size(text: str) -> int | None:
    m = re.search(r"([\d.]+)\s*(GB|MB|KB)", text or "")
    if not m:
        return None
    return int(float(m.group(1)) * {"GB": 10**9, "MB": 10**6, "KB": 10**3}[m.group(2)])


def _bytes(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, names in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, n)) for n in names
                     if os.path.isfile(os.path.join(root, n)))
    return total


# ------------------------------------------------------------- sections ----

def _ocr_section() -> Section:
    from common.downloads import download_file
    from config import get_tessdata_dir
    from OCR.ocr_logic import downloadable_tessdata
    root = get_tessdata_dir()
    section = Section("ocr", "OCR languages (Tesseract)",
                      "Language data for OCR. English and orientation detection ship with MDMT.", root)
    for name, code in sorted(downloadable_tessdata().items()):
        path = os.path.join(root, f"{code}.traineddata")
        section.assets.append(Asset(
            f"ocr:{code}", "ocr", f"{name} ({code})", None, bundled=code in BUNDLED_TESSDATA,
            installed_fn=lambda p=path: os.path.isfile(p),
            download_fn=lambda cb, c=code, p=path: download_file(f"{TESSDATA_URL}/{c}.traineddata", p, cb),
            paths_fn=lambda p=path: [p]))
    return section


def _whisper_section() -> Section:
    from Audio_Transcription.transcription_logic import WHISPER_MODELS, download_model, is_model_installed, model_dir
    from config import get_whisper_models_dir
    root = get_whisper_models_dir()
    section = Section("whisper", "Whisper models (Audio Transcription)",
                      "CTranslate2 conversions of OpenAI Whisper (MIT), run with faster-whisper.", root)
    for name, info in WHISPER_MODELS.items():
        section.assets.append(Asset(
            f"whisper:{name}", "whisper", f"Whisper {name}", _parse_size(info["size"]), "MIT",
            installed_fn=lambda n=name: is_model_installed(n, root),
            download_fn=lambda cb, n=name: download_model(n, root, cb),
            paths_fn=lambda n=name: [model_dir(n, root)]))
    return section


def _translation_section() -> Section:
    from Translation import offline_translation as ot
    root = ot.translation_root()
    section = Section("translation", "Translation models (Argos Translate)",
                      "One model per direction; pairs without a direct model translate through English.", root)
    for p in sorted(ot.load_index(), key=lambda p: (p["from_name"], p["to_name"])):
        a, b = p["from_code"], p["to_code"]
        section.assets.append(Asset(
            f"translation:{a}_{b}", "translation", f"{p['from_name']} → {p['to_name']}", p.get("size"),
            installed_fn=lambda a=a, b=b: ot.is_installed(a, b),
            download_fn=lambda cb, a=a, b=b: ot.download_package(a, b, None, cb),
            paths_fn=lambda a=a, b=b: [ot.package_dir(a, b)],
            license_path_fn=lambda a=a, b=b: ot.readme_path(a, b)))
    return section


def _ner_section() -> Section:
    from config import get_models_dir
    from NLP.ner_onnx import NER_MODELS, download_model, is_model_installed, model_dir
    root = get_models_dir()
    section = Section("ner", "Named entity model (Named Entities, Relationships)", "", os.path.join(root, "ner"))
    for key, info in NER_MODELS.items():
        section.assets.append(Asset(
            f"ner:{key}", "ner", info["name"], _parse_size(info["size"]),
            f"{info['languages']}. Labels: {', '.join(info['labels'])}. License: {info['license']}.",
            installed_fn=lambda k=key: is_model_installed(k),
            download_fn=lambda cb, k=key: download_model(k, None, cb),
            paths_fn=lambda k=key: [model_dir(k, root)]))
    return section


def _rag_in_use(path_of_model) -> str | None:
    from RAG.state import STATE
    session = STATE.session
    if session is None:
        return None
    used = {getattr(session.settings, "llm_path", None)}
    if path_of_model in used or STATE.setup.running:
        return "RAGBot is using this model: choose Change setup on the RAGBot page first."
    return None


def _retrieval_section() -> Section:
    from RAG import models
    section = Section("retrieval", "Retrieval models (RAGBot)",
                      "RAGBot also downloads these on first start if they are missing.", models.models_root())
    roles = {models.EMBEDDER["key"]: "Required: finds the passages relevant to a question.",
             models.RERANKER["key"]: "Optional (\"Rerank passages\"): reorders them for accuracy."}
    for info in models.RAG_MODELS.values():
        section.assets.append(Asset(
            f"retrieval:{info['key']}", "retrieval", info["name"], _parse_size(info["size"]),
            f"{roles[info['key']]} Multilingual. License: {info['license']}.",
            installed_fn=lambda i=info: models.is_installed(i),
            download_fn=lambda cb, i=info: models.download(i, None, cb),
            paths_fn=lambda i=info: [models.model_dir(i)],
            in_use_fn=lambda: "RAGBot is using the retrieval models: choose Change setup on the RAGBot page"
                              " first." if _rag_session_open() else None))
    return section


def _rag_session_open() -> bool:
    from RAG.state import STATE
    return STATE.session is not None or STATE.setup.running


def _llm_section() -> Section:
    from config import get_models_dir
    from RAG import models
    section = Section("llm", "Chat models (RAGBot)", f"Qwen 3.5, quantised GGUF. License: {models.QWEN_LICENSE}.",
                      get_models_dir())
    for key, info in models.QWEN_MODELS.items():
        section.assets.append(Asset(
            f"llm:{key}", "llm", info["name"], info["bytes"], info["desc"],
            installed_fn=lambda k=key: os.path.isfile(models.llm_path(k)),
            download_fn=lambda cb, k=key: models.download_llm(k, None, cb),
            paths_fn=lambda k=key: [models.llm_path(k)],
            in_use_fn=lambda k=key: _rag_in_use(models.llm_path(k))))
    # Other .gguf files (an older MDMT's 0.8B model, or the user's own) can still be deleted here.
    listed = {info["filename"] for info in models.QWEN_MODELS.values()}
    root = get_models_dir()
    for name in sorted(f for f in os.listdir(root) if f.endswith(".gguf") and f not in listed):
        path = os.path.join(root, name)
        section.assets.append(Asset(
            f"llm:file:{name}", "llm", name, None, "Not in the current list (an older download, or one you added).",
            installed_fn=lambda p=path: os.path.isfile(p), download_fn=None,
            paths_fn=lambda p=path: [p], in_use_fn=lambda p=path: _rag_in_use(p)))
    return section


def sections() -> list[Section]:
    return [_ocr_section(), _whisper_section(), _translation_section(), _ner_section(), _retrieval_section(),
            _llm_section()]


def section(section_id: str) -> Section:
    return next(s for s in sections() if s.id == section_id)


def find(key: str) -> Asset:
    builders = {"ocr": _ocr_section, "whisper": _whisper_section, "translation": _translation_section,
                "ner": _ner_section, "retrieval": _retrieval_section, "llm": _llm_section}
    return next(a for a in builders[key.split(":")[0]]().assets if a.key == key)


def section_bytes(sec: Section) -> int:
    return sum(a.disk_bytes() for a in sec.assets)


RECOMMENDED_WHISPER = "small"


def recommended(llm: str | None = None) -> list[Asset]:
    """The Welcome page's one-click setup: something for every tool."""
    if llm is None:
        from RAG.hardware import detect_hardware
        llm = detect_hardware().recommended_model
    from NLP.ner_onnx import DEFAULT_NER_MODEL
    from RAG import models
    keys = ["ocr:eng", "ocr:osd", f"whisper:{RECOMMENDED_WHISPER}", f"ner:{DEFAULT_NER_MODEL}",
            f"retrieval:{models.EMBEDDER['key']}", f"retrieval:{models.RERANKER['key']}", f"llm:{llm}"]
    return [find(k) for k in keys]
