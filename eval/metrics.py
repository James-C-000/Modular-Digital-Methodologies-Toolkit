"""Relevance judgements and retrieval / answer metrics.

A retrieved chunk is relevant to a question when it comes from a gold file and
contains one of that file's gold quotes (compared after normalize()).
"""
import re
import unicodedata

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"', "—": "-", "–": "-"})


def normalize(text: str) -> str:
    """NFKC, straight quotes and dashes, lower case, single spaces."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return re.sub(r"\s+", " ", text).strip()


def fold(text: str) -> str:
    """normalize() without accents, for matching short answers across spellings."""
    decomposed = unicodedata.normalize("NFKD", normalize(text))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_relevant(file: str, text: str, gold: list[dict]) -> bool:
    body = normalize(text)
    return any(g["file"] == file and normalize(g["quote"]) in body for g in gold)


def first_relevant_rank(ranked: list[tuple[str, str]], gold: list[dict]) -> int | None:
    """1-based rank of the first relevant (file, text) in *ranked*, or None."""
    for rank, (file, text) in enumerate(ranked, 1):
        if is_relevant(file, text, gold):
            return rank
    return None


def recall_at(ranks: list[int | None], k: int) -> float:
    """Share of questions with a relevant chunk in the top k."""
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks: list[int | None]) -> float:
    return sum(1 / r for r in ranks if r is not None) / len(ranks) if ranks else 0.0


def contains_term(text: str, term: str) -> bool:
    """*term* occurs in *text* as whole words (case, accents and quote style ignored)."""
    return re.search(r"(?<!\w)" + re.escape(fold(term)) + r"(?!\w)", fold(text)) is not None


def answer_matches(answer: str, accepted: list[str]) -> bool:
    return any(contains_term(answer, a) for a in accepted)
