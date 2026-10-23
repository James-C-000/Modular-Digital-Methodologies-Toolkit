import os

import pytest

from common.pdf_text import extract_pages, extract_text

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_extracts_each_page_in_order():
    pages = extract_pages(os.path.join(FIX, "text_sample.pdf"))
    assert len(pages) == 2
    assert "москва" in pages[0] and "Lisbon" in pages[0]
    assert "Ada Lovelace" in pages[1]
    assert all("\r" not in p for p in pages)


def test_image_only_pdf_has_empty_pages():
    pages = extract_pages(os.path.join(FIX, "ocr_sample.pdf"))
    assert pages == [""]


def test_extract_text_joins_pages():
    text = extract_text(os.path.join(FIX, "text_sample.pdf"))
    assert "Lisbon" in text and "Ada Lovelace" in text


def test_missing_file_raises(tmp_path):
    with pytest.raises(Exception):
        extract_pages(str(tmp_path / "nope.pdf"))
