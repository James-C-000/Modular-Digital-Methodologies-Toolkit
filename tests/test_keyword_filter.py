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


def test_keeps_line_breaks_and_hyphens_so_words_do_not_merge():
    assert basic_filter("the mill-\nrace\tflooded.") == "the mill-\nrace\tflooded"
    assert basic_filter("the mill-race, 1843–1851") == "the mill-race 18431851"   # only the hyphen-minus


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



def test_pdf_without_text_is_skipped_not_counted(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    shutil.copy(PDF, src / "sample.pdf")
    shutil.copy(os.path.join(os.path.dirname(PDF), "ocr_sample.pdf"), src / "scan.pdf")  # no text layer
    summary = search_directory(str(src), str(out), "москва\nzanzibar", basic=True, context_words=6)
    assert summary["files"] == 1 and summary["total"] == 2 and summary["hits"] == 2
    assert summary["skipped"] == [{"input": "scan.pdf", "message": "no text (scanned PDF? run OCR first)"}]
    assert not (out / "scan.pdf-PIE.png").exists()
    with open(out / "Data_Overview.csv", encoding="utf-8-sig", newline="") as f:
        assert [r[0] for r in list(csv.reader(f))[1:]] == ["sample.pdf"]


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
    with pytest.raises(ValueError, match="No keywords to search for"):
        search_directory(str(tmp_path), out, " \n\n  \n")
    (tmp_path / "blank.txt").write_text("\n  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="No keywords to search for: enter one per line in the keyword file"):
        search_directory(str(tmp_path), out, keyword_file=str(tmp_path / "blank.txt"))


def _text_pdf(path, pages):
    import matplotlib
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf"))
    for text in pages:
        pdf.add_page()
        pdf.set_font("DejaVu", size=11)
        pdf.multi_cell(0, 7, text)
    pdf.output(str(path))


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))[1:]


def test_every_hit_is_counted_once_with_one_context_row(tmp_path):
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    _text_pdf(src / "a.pdf", [
        "Mill opens the page. The mill-race flooded the mill race; the Mill race again and the mill",
        "new york new york new york. c++ beats c and a.b is not axb. The the the end.",
    ])
    # Spaces around keywords, repeats, blank lines and regex characters are all plain keywords.
    keywords = "  Mill \n\nmill race\nmill-race\nNew   York\nc++\na.b\nthe the\nmill"
    files = {"mill": "mill.csv", "mill race": "mill race.csv", "mill-race": "mill-race.csv",
             "new york": "new york.csv", "c++": "c++.csv", "a.b": "a.b.csv", "the the": "the the.csv"}

    def search(**options):
        summary = search_directory(str(src), str(out), keywords, context_words=4, **options)
        with open(out / "Data_Overview.csv", encoding="utf-8-sig", newline="") as f:
            header, row = list(csv.reader(f))
        assert header == ["Year", *files]
        counts = dict(zip(header[1:], map(int, row[1:])))
        assert summary["hits"] == sum(counts.values())
        for keyword, name in files.items():
            assert len(_rows(out / name)) == counts[keyword], keyword
        return counts

    # Whole words: "mill" at both ends of the page and inside "mill-race"; "mill race" also as
    # "mill-race" and "mill race;" (punctuation at the edges of words is ignored, inside them it is not).
    counts = {"mill": 5, "mill race": 3, "mill-race": 1, "new york": 3, "c++": 1, "a.b": 1, "the the": 1}
    assert search() == counts
    assert [r[1:] for r in _rows(out / "mill.csv")][:2] == [["1", "mill opens"], ["1", "page. the mill race"]]
    assert [r[2] for r in _rows(out / "new york.csv")] == [   # contexts keep the text's punctuation
        "new york new york", "new york new york new york.", "new york new york new york. c++"]
    # The basic filter keeps hyphens, so "mill-race" still matches; "c++" and "a.b" lose their symbols.
    assert search(basic=True) == dict(counts, **{"c++": 0, "a.b": 0})


@pytest.mark.parametrize("length, context", [
    (1, "key"), (2, "three key"), (3, "three key five"), (4, "two three key five"),
    (5, "two three key five six"), (6, "one two three key five six"),
])
def test_context_length_counts_the_keyword_and_splits_evenly(tmp_path, length, context):
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    _text_pdf(src / "a.pdf", ["one two three key five six seven"])
    search_directory(str(src), str(out), "key", context_words=length)
    assert [r[2] for r in _rows(out / "key.csv")] == [context]
