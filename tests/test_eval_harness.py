"""The RAG evaluation harness: corpus cleanup, relevance judgements and metrics."""
import json
import os

import pytest

from eval.fetch_corpus import strip_gutenberg
from eval.metrics import answer_matches, first_relevant_rank, is_relevant, mrr, normalize, recall_at

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")


def test_normalize_folds_quotes_case_and_whitespace():
    assert normalize("J’attends  mon\nmaître, “M. Vanderdendur”") == 'j\'attends mon maître, "m. vanderdendur"'


def test_relevance_needs_the_right_file_and_the_gold_quote():
    gold = [{"file": "a.txt", "quote": "a necessary   evil"}]
    assert is_relevant("a.txt", "government is but A necessary\nevil; in its worst", gold)
    assert not is_relevant("b.txt", "government is but a necessary evil", gold)
    assert not is_relevant("a.txt", "government is but a necessary", gold)


def test_ranks_and_metrics():
    gold = [{"file": "a.txt", "quote": "needle"}]
    ranked = [("b.txt", "needle"), ("a.txt", "hay"), ("a.txt", "the needle")]
    assert first_relevant_rank(ranked, gold) == 3
    assert first_relevant_rank(ranked[:2], gold) is None
    ranks = [1, 3, None, 7]
    assert recall_at(ranks, 1) == 0.25 and recall_at(ranks, 3) == 0.5 and recall_at(ranks, 10) == 0.75
    assert mrr(ranks) == pytest.approx((1 + 1 / 3 + 0 + 1 / 7) / 4)


def test_answer_matching_is_accent_and_case_insensitive():
    assert answer_matches("He was born in TUCKAHOE, Maryland [1].", ["Tuckahoe"])
    assert answer_matches("Pangloss taught metaphysico-theologo-cosmolonigology", ["cosmolonigolog"])
    assert answer_matches("Il est manichéen.", ["manicheen"])
    assert not answer_matches("He was born in Easton.", ["Tuckahoe", "Talbot"])


def test_strip_gutenberg_keeps_only_the_book():
    raw = ("The Project Gutenberg eBook of X\nlicense blah\n"
           "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\nChapter 1\nText.\n\n"
           "*** END OF THE PROJECT GUTENBERG EBOOK X ***\nmore license\n")
    assert strip_gutenberg(raw) == "Chapter 1\nText."


def test_question_set_is_well_formed():
    with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as f:
        files = {d["file"] for d in json.load(f)["documents"]}
    with open(os.path.join(EVAL_DIR, "questions.jsonl"), encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    assert len(questions) >= 40
    assert len({q["id"] for q in questions}) == len(questions)
    for q in questions:
        assert q["type"] in {"factual", "paraphrase", "cross-lingual", "unanswerable"}, q["id"]
        if q["type"] == "unanswerable":
            assert not q["gold"] and not q["answers"], q["id"]
        else:
            assert q["gold"] and q["answers"], q["id"]
            assert all(g["file"] in files and len(g["quote"].split()) <= 20 for g in q["gold"]), q["id"]
