import os

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
