"""PDF/A output needs Ghostscript, which MDMT does not bundle (AGPL).

v2.0.7 offered the PDF/A checkbox unconditionally and every run failed with
"Could not find program 'gs' on the PATH" on machines without Ghostscript.
"""
import shutil

import pytest

from OCR import ocr_logic
from OCR.ocr_logic import find_ghostscript


def test_missing_ghostscript_is_reported(monkeypatch):
    monkeypatch.setattr(ocr_logic.sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: None)
    assert find_ghostscript() is None


def test_posix_looks_for_gs(monkeypatch):
    seen = []
    monkeypatch.setattr(ocr_logic.sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: seen.append(name) or f"/opt/{name}")
    assert find_ghostscript() == "/opt/gs"
    assert seen == ["gs"]


def test_windows_looks_for_64bit_console_gs_only(monkeypatch):
    """ocrmypdf only runs gswin64c; a gswin32c install would still fail."""
    seen = []
    monkeypatch.setattr(ocr_logic.sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: seen.append(name) or None)
    assert find_ghostscript() is None
    assert seen == ["gswin64c"]


@pytest.mark.skipif(shutil.which("gs") is not None, reason="Ghostscript is installed here")
def test_pdfa_really_fails_without_ghostscript(tmp_path):
    """Documents why the checkbox must be gated: ocrmypdf cannot make PDF/A without gs."""
    import os
    from OCR.ocr_logic import run_ocr_file
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract not installed")
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "ocr_sample.pdf")
    result = run_ocr_file(fixture, str(tmp_path / "o.pdf"), ["eng"], output_type="pdfa")
    assert result["status"] == "error"
    assert "gs" in result["message"]
