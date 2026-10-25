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
    assert [r[1:] for r in _rows(out / "mill.csv")][:2] == [["1", "mill opens"], ["1", "page. the mill-race"]]
    assert [r[2] for r in _rows(out / "new york.csv")] == [   # contexts keep the text's punctuation
        "new york new york", "new york new york new york.", "new york new york new york. c++"]
    # The basic filter keeps hyphens, so "mill-race" still matches; "c++" and "a.b" lose their symbols
    # in the keywords as in the text, so they are searched as "c" (twice in "c beats c") and "ab".
    assert search(basic=True) == dict(counts, **{"c++": 2, "a.b": 1})


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


def _search_pages(tmp_path, monkeypatch, pages, keywords, **options):
    """Search one PDF whose pages have the text *pages*; the summary and the rows of each keyword's CSV."""
    from Advanced_Keyword_Search import advancedKeywordSearchLogic
    monkeypatch.setattr(advancedKeywordSearchLogic, "extract_pages", lambda path: pages)
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    (src / "a.pdf").write_bytes(b"")
    summary = search_directory(str(src), str(out), keywords, **options)
    return summary, {p.name: _rows(p) for p in out.glob("*.csv") if p.name != "Data_Overview.csv"}


def test_filters_apply_to_the_keywords_too(tmp_path, monkeypatch):
    # Filtering only the text turned "o'brien" into "obrien" there and found nothing.
    pages = ["O'Brien met the U.S. envoy by the mill-race."]
    summary, rows = _search_pages(tmp_path, monkeypatch, pages, "o'brien\nu.s.\nmill-race", basic=True)
    assert summary["hits"] == 3
    assert rows["o'brien.csv"][0][2] == "obrien met the"
    summary, rows = _search_pages(tmp_path, monkeypatch, pages, "mill-race", filters="-")
    assert summary["hits"] == 1 and rows["mill-race.csv"][0][2] == "by the millrace."


def test_contexts_keep_hyphens_and_minus_signs(tmp_path, monkeypatch):
    pages = ["the mill-race flooded in 1843-1851 at -5 degrees and the mill-\nrace"]
    _summary, rows = _search_pages(tmp_path, monkeypatch, pages, "in\nat\ndegrees\nthe", context_words=5)
    assert [r[2] for r in rows["in.csv"]] == ["race flooded in 1843-1851"]
    assert [r[2] for r in rows["at.csv"]] == ["1843-1851 at -5 degrees"]
    assert [r[2] for r in rows["degrees.csv"]] == ["at -5 degrees and the"]
    assert [r[2] for r in rows["the.csv"]] == ["the mill-race", "degrees and the mill- race"]


def test_ligatures_and_separate_accents_match_typed_keywords(tmp_path, monkeypatch):
    pages = ["the \ufb01eld o\ufb03ce of the cafe\u0301"]
    summary, rows = _search_pages(tmp_path, monkeypatch, pages, "field\noffice\ncafé\ncafe\u0301", context_words=1)
    assert summary["hits"] == 3 and sorted(rows) == ["café.csv", "field.csv", "office.csv"]
    assert rows["café.csv"] == [["a.pdf", "1", "café"]]


def test_separate_accents_in_a_real_pdf_match(tmp_path):
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    _text_pdf(src / "a.pdf", ["the cafe\u0301 opens"])   # the text layer keeps the accent as a separate mark
    assert search_directory(str(src), str(out), "café", basic=True)["hits"] == 1


def test_filter_characters_that_unicode_would_rewrite_still_work(tmp_path, monkeypatch):
    # Full NFKC normalization turned "™" into "TM" before the filter could remove it.
    summary, rows = _search_pages(tmp_path, monkeypatch, ["acme™ sells ²"], "acme", filters="™²")
    assert summary["hits"] == 1 and rows["acme.csv"][0][2] == "acme sells"


def test_filters_match_the_text_as_written_and_as_compared(tmp_path, monkeypatch):
    # A filtered ligature removed nothing: the text's "ﬁ" was already "fi" when the filter ran.
    summary, rows = _search_pages(tmp_path, monkeypatch, ["the ﬁeld"], "eld", filters="ﬁ", context_words=2)
    assert summary["hits"] == 1 and rows["eld.csv"][0][2] == "the eld"
    # A letter filtered out is also removed where a ligature spells it, in the text as in the keyword.
    summary, rows = _search_pages(tmp_path, monkeypatch, ["the ﬁeld"], "field", filters="f", context_words=1)
    assert summary["hits"] == 1 and rows["field.csv"][0][2] == "ield"
    # An "é" typed as "e" and a separate accent removed every "e".
    summary, rows = _search_pages(tmp_path, monkeypatch, ["café cafe"], "caf", filters="e\u0301", context_words=1)
    assert summary["hits"] == 1 and rows["caf.csv"][0][2] == "caf"


def test_spacing_accents_as_latex_pdfs_extract_them_join_their_letters(tmp_path, monkeypatch):
    # LaTeX PDFs extract "café" as "caf´e": NFKC made that two words, and 2.2.2 kept the accent apart from the "e".
    pages = ["the caf´e of M¨uller and Dvoˇr´ak, it´s said"]
    keywords = "café\nmüller\ndvořák\nit´s"
    for options in ({}, {"basic": True}):
        summary, rows = _search_pages(tmp_path, monkeypatch, pages, keywords, context_words=1, **options)
        assert summary["hits"] == 4, options
        assert rows["café.csv"] == [["a.pdf", "1", "café"]] and rows["dvořák.csv"][0][2].rstrip(",") == "dvořák"
    # "´" also stands in for an apostrophe, so it only joins a vowel: "it´s" is not "itś".
    summary, rows = _search_pages(tmp_path, monkeypatch, pages, "its", basic=True, context_words=1)
    assert rows["its.csv"] == [["a.pdf", "1", "its"]]


def test_compatibility_forms_of_letters_match_typed_keywords(tmp_path, monkeypatch):
    # PDFs often extract Arabic as presentation forms; 2.2.2 stopped mapping these (and fullwidth letters).
    pages = ["\ufee3\ufeae\ufea3\ufe92\ufe8e and ＡＢＣ １２"]
    summary, rows = _search_pages(tmp_path, monkeypatch, pages, "مرحبا\nabc\n12", context_words=1)
    assert summary["hits"] == 3 and rows["مرحبا.csv"] == [["a.pdf", "1", "مرحبا"]]


def test_keywords_that_compare_alike_are_searched_once_and_reported(tmp_path, monkeypatch):
    summary, rows = _search_pages(tmp_path, monkeypatch, ["New York, new york."], "york\nyork.\n(York)\nYORK")
    assert summary["hits"] == 2 and list(rows) == ["york.csv"]
    with open(tmp_path / "out" / "Data_Overview.csv", encoding="utf-8-sig", newline="") as f:
        assert next(csv.reader(f)) == ["Year", "york"]
    assert summary["keyword_notes"] == ['"york." was counted as "york": they match the same words.',
                                        '"(york)" was counted as "york": they match the same words.']


def test_keywords_the_filter_makes_alike_are_reported(tmp_path, monkeypatch):
    # With the basic filter "c++" and "c#" are both "c": c# used to vanish without a word.
    summary, rows = _search_pages(tmp_path, monkeypatch, ["c# and c"], "c++\nc#", basic=True)
    assert summary["hits"] == 2 and list(rows) == ["c++.csv"]
    assert summary["keyword_notes"] == ['"c#" was counted as "c++": they match the same words.']


def test_a_keyword_the_filter_empties_is_never_found_and_reported(tmp_path, monkeypatch):
    # Repeated after another emptied keyword, "++" was searched again as "++ (2)".
    summary, rows = _search_pages(tmp_path, monkeypatch, ["a + b ++ c ##"], "++\nb\n##\n++\n##", basic=True)
    assert summary["hits"] == 1 and rows["++.csv"] == [] and rows["##.csv"] == [] and "++ (2).csv" not in rows
    assert summary["keyword_notes"] == ['"++" was not searched: the filter leaves nothing of it.',
                                        '"##" was not searched: the filter leaves nothing of it.']


def test_keywords_a_case_sensitive_filter_tells_apart_are_both_searched(tmp_path, monkeypatch):
    # Filtering "Y" makes "York" "ork" but leaves "york": the second keyword used to be dropped.
    summary, rows = _search_pages(tmp_path, monkeypatch, ["York york"], "York\nyork", filters="Y", context_words=1)
    assert summary["hits"] == 2 and summary["keyword_notes"] == []
    assert rows["york.csv"] == [["a.pdf", "1", "ork"]] and rows["york (2).csv"] == [["a.pdf", "1", "york"]]


def test_a_keyword_named_like_the_overview_gets_its_own_csv(tmp_path, monkeypatch):
    # On Windows and macOS "data_overview.csv" is Data_Overview.csv, so the two reports overwrote each other.
    _summary, rows = _search_pages(tmp_path, monkeypatch, ["see data_overview"], "data_overview")
    assert rows["data_overview_2.csv"] == [["a.pdf", "1", "see data_overview"]]
    assert "data_overview.csv" not in rows


def test_charts_show_dollar_signs_and_a_chart_failure_skips_only_the_charts(tmp_path):
    from tests.test_encoding import PDF
    src, out = tmp_path / "pdfs", tmp_path / "out"
    (src / "box").mkdir(parents=True)
    out.mkdir()
    shutil.copy(PDF, src / "price $^$.pdf")          # matplotlib read "$^$" as mathematics and failed
    shutil.copy(PDF, src / "box" / "letters.pdf")
    shutil.copy(PDF, src / "z.pdf")
    (out / "box").write_text("a file where the chart folder should go", encoding="utf-8")
    summary = search_directory(str(src), str(out), "москва\n$x^$")
    assert summary["files"] == summary["total"] == 3 and summary["hits"] == 6
    assert summary["skipped"] == []   # searched, so listed as a warning instead
    assert [w["input"] for w in summary["warnings"]] == [os.path.join("box", "letters.pdf")]
    assert summary["warnings"][0]["message"].startswith("searched, but its charts could not be saved")
    assert (out / "price $^$.pdf-PIE.png").stat().st_size > 0 and (out / "z.pdf-BAR.png").is_file()
    assert all(os.path.isfile(c) for c in summary["charts"])
    assert {r[0] for r in _rows(out / "москва.csv")} == {"price $^$.pdf", os.path.join("box", "letters.pdf"), "z.pdf"}


def test_total_charts_that_cannot_be_saved_do_not_fail_the_search(tmp_path, monkeypatch):
    (tmp_path / "out" / "totalPie.png").mkdir(parents=True)   # a folder where the chart should go
    summary, rows = _search_pages(tmp_path, monkeypatch, ["the key"], "key")
    assert summary["hits"] == 1 and rows["key.csv"] and summary["charts"] == [str(tmp_path / "out" / "totalBar.png")]
    assert [w["input"] for w in summary["warnings"]] == ["totalPie.png"]


def test_any_chart_error_loses_only_that_chart_and_leaves_no_old_one(tmp_path, monkeypatch):
    # Only OSError and ValueError were caught, so Agg's OverflowError stopped the search; and a pie saved
    # before a failing bar chart, or a chart from an earlier search, stayed on disk while reported as not saved.
    from Advanced_Keyword_Search import advancedKeywordSearchLogic

    def fail(*_args):
        raise OverflowError("Exceeded cell block limit")

    monkeypatch.setattr(advancedKeywordSearchLogic, "_save_bar", fail)
    out = tmp_path / "out"
    out.mkdir()
    (out / "totalBar.png").write_bytes(b"a chart from an earlier search")
    summary, rows = _search_pages(tmp_path, monkeypatch, ["the key"], "key")
    assert summary["hits"] == 1 and rows["key.csv"]
    assert summary["charts"] == [str(out / "totalPie.png")] and (out / "a.pdf-PIE.png").stat().st_size > 0
    assert not (out / "totalBar.png").exists() and not (out / "a.pdf-BAR.png").exists()
    assert summary["warnings"] == [
        {"input": "a.pdf", "message": "searched, but its bar chart could not be saved (Exceeded cell block limit)"},
        {"input": "totalBar.png", "message": "could not be saved (Exceeded cell block limit)"}]
