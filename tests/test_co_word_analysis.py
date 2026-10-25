import os
import re
import shutil
from urllib.parse import unquote

from NLP.co_word_analysis import cooccurrence_analysis, main, preprocess_text
from NLP.text_utils import stopwords


def test_preprocess_keeps_non_ascii_words_and_drops_stopwords():
    tokens = preprocess_text("Le meunier et sa femme sont allés au moulin.", stopwords("fr"))
    assert tokens == ["meunier", "femme", "allés", "moulin"]


def test_cooccurrence_window():
    counts = cooccurrence_analysis(["mill", "river", "mill", "grain"], window_size=2)
    assert counts[("mill", "river")] == 2 and counts[("grain", "mill")] == 1


def test_end_to_end_with_stopwords_and_custom_words(tmp_path):
    text = ("The miller sold grain at the market. The miller paid the toll at the bridge. "
            "Grain prices rose at the market after the flood. ") * 5
    (tmp_path / "ledger.txt").write_text(text, encoding="utf-8")
    main(str(tmp_path), stopword_language="en", extra_stopwords={"toll"})
    report = (tmp_path / "ledger_co_word_analysis.html").read_text(encoding="utf-8")
    assert "<td>miller</td>" in report and "<td>grain</td>" in report
    assert "<td>the</td>" not in report and "<td>toll</td>" not in report
    assert (tmp_path / "ledger_co_word_network.png").stat().st_size > 0
    assert os.path.exists(tmp_path / "Co_Word_Analysis_Summary.html")


def test_file_names_are_escaped_in_reports(tmp_path):
    name = "a&b.txt"
    (tmp_path / name).write_text("mill river mill river grain " * 10, encoding="utf-8")
    main(str(tmp_path), stopword_language=None)
    summary = (tmp_path / "Co_Word_Analysis_Summary.html").read_text(encoding="utf-8")
    assert "a&amp;b.txt" in summary


def test_summary_links_reach_reports_in_subfolders(tmp_path):
    (tmp_path / "box 1#").mkdir()
    (tmp_path / "box 1#" / "letters.txt").write_text("mill river grain mill river grain " * 5, encoding="utf-8")
    main(str(tmp_path), stopword_language=None)
    summary = (tmp_path / "Co_Word_Analysis_Summary.html").read_text(encoding="utf-8")
    links = re.findall(r"href='([^']+)'", summary)
    assert links == ["box%201%23/letters_co_word_analysis.html"]
    assert (tmp_path / unquote(links[0])).is_file()


def test_legacy_encoded_text_is_analysed_and_empty_files_are_reported(tmp_path):
    (tmp_path / "old.txt").write_bytes("Café owners wrote letters about the café trade. ".encode("cp1252") * 5)
    (tmp_path / "blank.txt").write_text("  \n", encoding="utf-8")
    summary = main(str(tmp_path), stopword_language="en")
    assert summary["files"] == 1 and summary["total"] == 2
    assert summary["skipped"] == [{"input": "blank.txt", "message": "no text (scanned PDF? run OCR first)"}]
    assert "<td>café</td>" in (tmp_path / "old_co_word_analysis.html").read_text(encoding="utf-8")


def test_a_pdf_and_a_text_file_with_the_same_name_get_separate_reports(tmp_path):
    shutil.copy(os.path.join(os.path.dirname(__file__), "fixtures", "text_sample.pdf"), tmp_path / "doc.pdf")
    (tmp_path / "doc.txt").write_text("mill river grain mill river grain " * 5, encoding="utf-8")
    assert main(str(tmp_path), stopword_language=None)["files"] == 2
    assert (tmp_path / "doc_co_word_analysis.html").read_text(encoding="utf-8").count("doc.pdf") == 2
    assert "doc.txt" in (tmp_path / "doc_2_co_word_analysis.html").read_text(encoding="utf-8")
