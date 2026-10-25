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
