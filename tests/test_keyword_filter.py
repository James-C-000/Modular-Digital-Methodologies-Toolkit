"""Keyword search's basic filter keeps letters of every script."""
import csv
import os
import shutil

from Advanced_Keyword_Search.advancedKeywordSearchLogic import basic_filter, core_logic

def test_keeps_accented_and_non_latin_letters_and_digits():
    assert basic_filter("Café São Paulo — Москва, 1851! Kraków & Ελλάδα; 北京") == \
        "Café São Paulo  Москва 1851 Kraków  Ελλάδα 北京"


def test_keeps_accents_written_as_combining_marks():
    decomposed = "Café"          # e + combining acute, as some PDFs store it
    assert basic_filter(decomposed + "!") == decomposed


def test_keeps_line_breaks_so_words_do_not_merge():
    assert basic_filter("the mill-\nrace\tflooded.") == "the mill\nrace\tflooded"


def test_drops_punctuation_symbols_and_ocr_noise():
    assert basic_filter("§ ¶ | ~ * # ^ _ « » “ ” • ©") == " " * 13   # only the spaces between them


def test_search_with_the_basic_filter_finds_non_latin_keywords(tmp_path):
    # The ASCII-only filter used to delete "москва" before searching.
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "sample.pdf")
    errors = []
    summary = core_logic("6", 1, str(src), str(out), "", "москва", "", "", on_error=errors.append)
    assert not errors and summary["files"] == 1
    with open(out / "москва.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 3 and all("москва" in r[2] for r in rows[1:])
