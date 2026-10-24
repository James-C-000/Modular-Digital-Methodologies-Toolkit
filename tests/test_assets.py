"""The registry of downloadable assets behind the Downloads and Welcome pages."""
import os

import pytest

import config
from common import assets


@pytest.fixture(autouse=True)
def app_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: str(tmp_path))
    return tmp_path


def test_every_registry_is_listed():
    from Audio_Transcription.transcription_logic import WHISPER_MODELS
    from OCR.ocr_logic import downloadable_tessdata
    from RAG.models import QWEN_MODELS
    from Translation.offline_translation import load_index
    by_id = {s.id: s for s in assets.sections()}
    assert list(by_id) == ["ocr", "whisper", "translation", "ner", "retrieval", "llm"]
    assert len(by_id["ocr"].assets) == len(downloadable_tessdata())
    assert len(by_id["whisper"].assets) == len(WHISPER_MODELS)
    assert len(by_id["translation"].assets) == len(load_index())
    assert len(by_id["llm"].assets) == len(QWEN_MODELS)
    assert [a.key for a in by_id["retrieval"].assets] == ["retrieval:multilingual-e5-small",
                                                          "retrieval:bge-reranker-v2-m3"]
    keys = [a.key for s in by_id.values() for a in s.assets]
    assert len(keys) == len(set(keys))


def test_sizes_are_known_where_the_registry_says():
    assert assets.find("whisper:small").size == 486 * 10**6
    assert assets.find("llm:2B").size == 1280835840
    assert assets.find("translation:fr_en").size > 10**7
    assert assets.find("ocr:fra").size is None          # Tesseract files: size unknown until downloaded


def test_installed_delete_and_disk_usage(app_data):
    whisper = assets.find("whisper:tiny")
    assert not whisper.installed()
    folder = app_data / "whisper_models" / "tiny"
    folder.mkdir(parents=True)
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (folder / name).write_bytes(b"x" * 100)
    assert whisper.installed() and whisper.disk_bytes() == 400
    assert assets.section_bytes(assets.section("whisper")) == 400
    whisper.delete()
    assert not whisper.installed() and not folder.exists()


def test_bundled_languages_cannot_be_deleted(app_data):
    eng = assets.find("ocr:eng")
    assert eng.bundled
    with pytest.raises(RuntimeError):
        eng.delete()
    assert not assets.find("ocr:fra").bundled


def test_llm_lands_in_the_models_folder(app_data, monkeypatch):
    calls = []
    import common.hf_models as hf
    monkeypatch.setattr(hf, "download_file", lambda repo, rev, name, target, on_progress=None:
                        calls.append((repo, rev, name, target, on_progress)) or target)
    progress = object()
    assets.find("llm:0.8B").download(progress)
    repo, rev, name, target, on_progress = calls[0]
    assert target == os.path.join(str(app_data), "models", "Qwen3.5-0.8B-Q4_K_M.gguf")
    assert len(rev) == 40 and on_progress is progress


def test_recommended_setup(monkeypatch):
    keys = [a.key for a in assets.recommended(llm="2B")]
    assert keys == ["ocr:eng", "ocr:osd", "whisper:small", "ner:multilingual",
                    "retrieval:multilingual-e5-small", "retrieval:bge-reranker-v2-m3", "llm:2B"]


def test_human_bytes():
    assert assets.human_bytes(None) == "?"
    assert assets.human_bytes(512) == "512 B"
    assert assets.human_bytes(135 * 10**6) == "135 MB"
    assert assets.human_bytes(2740937888) == "2.74 GB"
