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


def test_a_hyphen_ending_a_line_is_kept_with_its_line_break(tmp_path):
    """PDFium turns "mill-" + newline + "race" into "mill\\x02race", which no keyword search could find."""
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in ("the great mill-", "race flooded and New-", "York was fine"):
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    path = str(tmp_path / "hyphens.pdf")
    pdf.output(path)
    text = extract_pages(path)[0]
    assert "\x02" not in text
    assert "mill-\nrace" in text and "New-\nYork" in text


def test_keyword_search_finds_words_split_at_a_line_end(tmp_path):
    fpdf = pytest.importorskip("fpdf")
    from Advanced_Keyword_Search.advancedKeywordSearchLogic import search_directory
    (tmp_path / "in").mkdir()
    (tmp_path / "out").mkdir()
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in ("the great mill-", "race flooded and New-", "York was fine"):
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(tmp_path / "in" / "a.pdf"))
    summary = search_directory(str(tmp_path / "in"), str(tmp_path / "out"), keywords="mill race\nyork\nrace")
    assert summary["hits"] == 3
