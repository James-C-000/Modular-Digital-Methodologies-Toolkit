"""Regression tests for the managed tessdata directory (v2.0.7 bug: languages
downloaded in-app were never used because ocrmypdf ignored ``tessdata_dir=``)."""
import inspect
import os
import shutil

import pytest

from OCR import tessdata
from OCR.tessdata import configure_tessdata, installed_languages, seed_tessdata

FIXTURE_PDF = os.path.join(os.path.dirname(__file__), "fixtures", "ocr_sample.pdf")


def _fake_source(root):
    src = root / "src_tessdata"
    (src / "configs").mkdir(parents=True)
    (src / "configs" / "hocr").write_text("tessedit_create_hocr 1\n")
    (src / "configs" / "txt").write_text("tessedit_create_txt 1\n")
    (src / "eng.traineddata").write_bytes(b"eng")
    (src / "osd.traineddata").write_bytes(b"osd")
    (src / "fra.traineddata").write_bytes(b"fra")
    (src / "pdf.ttf").write_bytes(b"ttf")
    return src


def test_seed_copies_eng_osd_and_support_files(tmp_path):
    src = _fake_source(tmp_path)
    managed = tmp_path / "managed"
    seed_tessdata(str(managed), str(src))
    assert installed_languages(str(managed)) == {"eng", "osd"}  # fra is not a seed language
    assert (managed / "configs" / "hocr").is_file()
    assert (managed / "configs" / "txt").is_file()
    assert (managed / "pdf.ttf").is_file()
    assert not list(managed.rglob("*.part"))


def test_seed_never_overwrites_existing_files(tmp_path):
    src = _fake_source(tmp_path)
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "eng.traineddata").write_bytes(b"user-downloaded")
    seed_tessdata(str(managed), str(src))
    assert (managed / "eng.traineddata").read_bytes() == b"user-downloaded"


def test_seed_with_missing_source_is_a_noop(tmp_path):
    assert seed_tessdata(str(tmp_path / "managed"), None) == []
    assert seed_tessdata(str(tmp_path / "managed"), str(tmp_path / "nope")) == []


def test_configure_sets_tessdata_prefix_to_managed_dir(tmp_path, monkeypatch):
    src = _fake_source(tmp_path)
    managed = tmp_path / "managed"
    monkeypatch.setattr(tessdata, "get_tessdata_dir", lambda: str(managed))
    monkeypatch.setattr(tessdata, "find_seed_source", lambda: str(src))
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    assert configure_tessdata() == str(managed)
    assert os.environ["TESSDATA_PREFIX"] == str(managed)
    assert {"eng", "osd"} <= installed_languages(str(managed))


def test_ocr_api_has_no_bogus_tessdata_kwarg():
    """ocrmypdf has no tessdata option; passing one is silently swallowed."""
    import ocrmypdf
    from OCR import ocr_logic
    assert "tessdata_dir" not in inspect.signature(ocrmypdf.ocr).parameters
    assert "tessdata_dir" not in inspect.signature(ocr_logic.run_ocr_batch).parameters
    assert not hasattr(__import__("pages.ocr", fromlist=["x"]), "_find_tessdata_dir")


def test_downloads_offer_every_registered_language_plus_osd():
    from OCR.ocr_logic import TESSERACT_LANGUAGES, downloadable_tessdata
    offered = downloadable_tessdata()
    assert set(TESSERACT_LANGUAGES.values()) <= set(offered.values())
    assert "osd" in offered.values()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_language_only_in_managed_dir_is_used(tmp_path, monkeypatch):
    """End-to-end: a language that exists only in the managed dir must work.

    The language is a renamed copy of eng ("mdmtonly"), so it cannot be found
    in any system tessdata directory -- only via TESSDATA_PREFIX.
    """
    from OCR.ocr_logic import run_ocr_file

    source = tessdata.find_seed_source()
    if source is None:
        pytest.skip("no system tessdata to seed from")
    managed = tmp_path / "managed"
    monkeypatch.setattr(tessdata, "get_tessdata_dir", lambda: str(managed))
    monkeypatch.setattr(tessdata, "find_seed_source", lambda: source)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    configure_tessdata()
    shutil.copyfile(managed / "eng.traineddata", managed / "mdmtonly.traineddata")

    out_pdf = tmp_path / "out.pdf"
    sidecar = tmp_path / "out.txt"
    result = run_ocr_file(FIXTURE_PDF, str(out_pdf), ["mdmtonly"], sidecar_path=str(sidecar))
    assert result["status"] == "success", result.get("message")
    assert "lighthouse" in sidecar.read_text(encoding="utf-8").lower()
