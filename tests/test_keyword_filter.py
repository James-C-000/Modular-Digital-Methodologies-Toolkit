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


def test_upper_case_pdf_extension_is_searched(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "SCAN.PDF")
    (src / "notes.txt").write_text("not a PDF", encoding="utf-8")
    errors = []
    summary = core_logic("6", 1, str(src), str(out), "", "москва", "", "", on_error=errors.append)
    assert not errors and summary["files"] == summary["total"] == 1


def test_keyword_and_filter_files_in_legacy_encodings(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "sample.pdf")
    (tmp_path / "keywords.txt").write_bytes("\ufeffмосква\r\nköln\r\n".encode("utf-8"))   # BOM, CRLF
    (tmp_path / "filters.txt").write_bytes("«»,;\r\n".encode("cp1252"))
    errors = []
    summary = core_logic("6", 0, str(src), str(out), str(tmp_path / "keywords.txt"), "",
                         str(tmp_path / "filters.txt"), "", on_error=errors.append)
    assert not errors and summary["files"] == 1
    assert sorted(p.name for p in out.glob("*.csv")) == ["Data_Overview.csv", "köln.csv", "москва.csv"]
    with open(out / "москва.csv", encoding="utf-8-sig", newline="") as f:
        assert len(list(csv.reader(f))) == 3


def test_pdfs_and_runs_without_hits_still_finish(tmp_path):
    # matplotlib cannot draw an empty pie: one PDF without hits used to stop the run.
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "sample.pdf")
    errors = []
    summary = core_logic("6", 1, str(src), str(out), "", "zanzibar", "", "", on_error=errors.append)
    assert not errors and summary["files"] == 1 and summary["hits"] == 0
    assert all((out / name).stat().st_size > 0
               for name in ("sample.pdf-PIE.png", "sample.pdf-BAR.png", "totalPie.png", "totalBar.png"))
    shutil.copy(os.path.join(os.path.dirname(PDF), "ocr_sample.pdf"), src / "scan.pdf")  # no text layer
    summary = core_logic("6", 1, str(src), str(out), "", "москва\nzanzibar", "", "", on_error=errors.append)
    assert not errors and summary["files"] == 2 and summary["hits"] == 2
    assert (out / "scan.pdf-PIE.png").stat().st_size > 0
