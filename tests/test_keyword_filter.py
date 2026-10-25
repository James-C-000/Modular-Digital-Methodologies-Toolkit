"""Keyword search: the basic filter keeps letters of every script; folders, files and errors."""
import csv
import os
import shutil

import pytest

from Advanced_Keyword_Search.advancedKeywordSearchLogic import basic_filter, search_directory


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
    summary = search_directory(str(src), str(out), "москва", basic=True, context_words=6)
    assert summary["files"] == 1
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
    summary = search_directory(str(src), str(out), "москва", basic=True, context_words=6)
    assert summary["files"] == summary["total"] == 1


def test_keyword_and_filter_files_in_legacy_encodings(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "sample.pdf")
    (tmp_path / "keywords.txt").write_bytes("\ufeffмосква\r\nköln\r\n".encode("utf-8"))   # BOM, CRLF
    (tmp_path / "filters.txt").write_bytes("«»,;\r\n".encode("cp1252"))
    summary = search_directory(str(src), str(out), keyword_file=str(tmp_path / "keywords.txt"),
                               filter_file=str(tmp_path / "filters.txt"), context_words=6)
    assert summary["files"] == 1
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
    summary = search_directory(str(src), str(out), "zanzibar", basic=True, context_words=6)
    assert summary["files"] == 1 and summary["hits"] == 0
    assert all((out / name).stat().st_size > 0
               for name in ("sample.pdf-PIE.png", "sample.pdf-BAR.png", "totalPie.png", "totalBar.png"))
    shutil.copy(os.path.join(os.path.dirname(PDF), "ocr_sample.pdf"), src / "scan.pdf")  # no text layer
    summary = search_directory(str(src), str(out), "москва\nzanzibar", basic=True, context_words=6)
    assert summary["files"] == 2 and summary["hits"] == 2
    assert (out / "scan.pdf-PIE.png").stat().st_size > 0


def test_sub_folders_are_searched_and_their_charts_mirrored(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    (src / "box1").mkdir(parents=True)
    (src / "box2").mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "top.pdf")
    shutil.copy(PDF, src / "box1" / "letters.pdf")
    shutil.copy(PDF, src / "box2" / "letters.pdf")   # same name in another folder
    summary = search_directory(str(src), str(out), "москва", context_words=6)
    assert summary["files"] == summary["total"] == 3 and summary["hits"] == 6
    for rel in (os.path.join("box1", "letters.pdf"), os.path.join("box2", "letters.pdf"), "top.pdf"):
        assert (out / (rel + "-PIE.png")).stat().st_size > 0 and (out / (rel + "-BAR.png")).is_file()
    with open(out / "Data_Overview.csv", encoding="utf-8-sig", newline="") as f:
        assert [r[0] for r in list(csv.reader(f))[1:]] == [
            os.path.join("box1", "letters.pdf"), os.path.join("box2", "letters.pdf"), "top.pdf"]
    with open(out / "москва.csv", encoding="utf-8-sig", newline="") as f:
        assert {r[0] for r in list(csv.reader(f))[1:]} == {
            os.path.join("box1", "letters.pdf"), os.path.join("box2", "letters.pdf"), "top.pdf"}


def test_unreadable_pdf_is_skipped_and_the_run_goes_on(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    (src / "box").mkdir(parents=True)
    out.mkdir()
    shutil.copy(PDF, src / "good.pdf")
    (src / "box" / "broken.pdf").write_bytes(b"not a PDF")
    summary = search_directory(str(src), str(out), "москва")
    assert summary["files"] == 1 and summary["total"] == 2 and summary["hits"] == 2
    assert [s["input"] for s in summary["skipped"]] == [os.path.join("box", "broken.pdf")]
    assert summary["skipped"][0]["message"].startswith("could not be read")


def test_problems_with_the_inputs_raise_clear_errors(tmp_path):
    (tmp_path / "out").mkdir()
    out = str(tmp_path / "out")
    with pytest.raises(NotADirectoryError):
        search_directory(str(tmp_path / "missing"), out, "москва")
    with pytest.raises(ValueError, match="Cannot read the keyword file"):
        search_directory(str(tmp_path), out, keyword_file=str(tmp_path / "missing.txt"))
    with pytest.raises(ValueError, match="Cannot search for the keyword 'c\\(\\+\\+'"):
        search_directory(str(tmp_path), out, "c(++")
