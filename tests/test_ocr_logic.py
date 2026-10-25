from OCR.ocr_logic import TESSERACT_LANGUAGES, build_ocr_params


def test_tesseract_languages_contains_english():
    assert "English" in TESSERACT_LANGUAGES
    assert TESSERACT_LANGUAGES["English"] == "eng"


def test_tesseract_languages_has_all_entries():
    assert len(TESSERACT_LANGUAGES) > 100


def test_build_ocr_params_basic():
    params = build_ocr_params(
        language_codes=["eng"],
        deskew=False,
        rotate_pages=False,
        rotate_threshold=15,
        redo_ocr=False,
        output_type="pdf",
        sidecar_path=None,
    )
    assert params["language"] == "eng"
    assert params["deskew"] is False
    assert params["rotate_pages"] is False
    assert params["output_type"] == "pdf"
    assert "sidecar" not in params
    assert "rotate_pages_threshold" not in params


def test_build_ocr_params_with_sidecar_and_rotation():
    params = build_ocr_params(
        language_codes=["eng", "fra"],
        deskew=True,
        rotate_pages=True,
        rotate_threshold=30,
        redo_ocr=False,
        output_type="pdfa",
        sidecar_path="/tmp/out.txt",
    )
    assert params["language"] == "eng+fra"
    assert params["sidecar"] == "/tmp/out.txt"
    assert params["rotate_pages_threshold"] == 30


def test_a_problem_ocrmypdf_returns_rather_than_raises_is_an_error(monkeypatch):
    """PDF/A conversion failure is a return code, with the output written anyway."""
    import ocrmypdf
    from OCR import ocr_logic
    monkeypatch.setattr(ocr_logic.ocrmypdf, "ocr", lambda *a, **k: ocrmypdf.ExitCode.pdfa_conversion_failed)
    result = ocr_logic.run_ocr_file("in.pdf", "out.pdf", ["eng"], output_type="pdfa")
    assert result["status"] == "error" and "not valid PDF/A" in result["message"]
    monkeypatch.setattr(ocr_logic.ocrmypdf, "ocr", lambda *a, **k: ocrmypdf.ExitCode.ok)
    assert ocr_logic.run_ocr_file("in.pdf", "out.pdf", ["eng"])["status"] == "success"
