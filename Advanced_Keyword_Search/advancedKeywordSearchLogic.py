"""Keyword search: count keywords in a folder of PDFs and collect their context.

Every PDF under the input folder, sub-folders included, is searched page by
page.  Keywords are plain text matched as whole words, ignoring case; a
keyword of several words matches them in sequence.  Hyphens separate words
unless the keyword contains one, so "mill race" also finds "mill-race".
Every occurrence is counted once and gets one row in the keyword's CSV.
The output folder receives:

- ``<keyword>.csv``: one row per hit with the PDF, the page and the words
  around the keyword;
- ``Data_Overview.csv``: how often each keyword occurs in each PDF;
- ``<pdf>-PIE.png`` and ``<pdf>-BAR.png``: one PDF's counts, in the matching
  sub-folder of the output folder for a PDF in a sub-folder;
- ``totalPie.png`` and ``totalBar.png``: the counts over every PDF.
"""
import csv
import logging
import os
import re
import unicodedata

from matplotlib.figure import Figure

from common.paths import find_files, unique_safe_filenames
from common.pdf_text import extract_pages
from common.text_files import read_text

log = logging.getLogger(__name__)

# CSVs are opened by researchers in Excel: UTF-8 with a BOM so non-Latin text
# displays correctly, and newline="" so the csv module controls line endings
# (otherwise Windows gets a blank line after every row).
CSV_ENCODING = "utf-8-sig"
OVERVIEW_CSV = "Data_Overview.csv"


def basic_filter(text: str) -> str:
    """Keep letters of any script (with their accents, also as combining marks),
    digits and whitespace; drop punctuation, symbols and OCR noise."""
    return "".join(ch for ch in text if ch.isspace() or unicodedata.category(ch)[0] in "LMN")


def _read_file(path: str, what: str) -> str:
    try:
        return read_text(path)
    except (OSError, ValueError) as e:
        raise ValueError(f"Cannot read the {what} file: {e}") from e


def _load_keywords(keywords: str, keyword_file: str) -> list[str]:
    """The keywords: one per line of the file if given, else of *keywords*.

    Lower-cased, with surrounding and repeated spaces removed; blank lines and
    repeats are left out.
    """
    text = _read_file(keyword_file, "keyword") if keyword_file else keywords
    found = list(dict.fromkeys(" ".join(line.split()).lower() for line in text.splitlines()))
    found = [k for k in found if k]
    if not found:
        raise ValueError("No keywords to search for: enter one per line" +
                         (" in the keyword file." if keyword_file else "."))
    return found


def _text_filter(basic: bool, filters: str, filter_file: str):
    """A function removing the characters the user filters out of a page's text."""
    if basic:
        return basic_filter
    if filter_file:
        remove = _read_file(filter_file, "filter").replace("\r", "").replace("\n", "")
    else:
        remove = filters.replace("\n", "")
    table = str.maketrans("", "", remove)
    return lambda text: text.translate(table)


def _split_words(text: str, hyphens_separate: bool) -> list[str]:
    return [w for w in re.split(r"[-\s]+", text) if w] if hyphens_separate else text.split()


def _tokens(words: list[str], keyword: str) -> list[str]:
    """*words* with each occurrence of a keyword of several words joined into one.

    Occurrences do not overlap: "the the" occurs once in "the the the".
    Words that continue on the next page are not joined.
    """
    parts = keyword.split()
    if len(parts) == 1:
        return words
    tokens, at = [], 0
    while at < len(words):
        if words[at:at + len(parts)] == parts:
            tokens.append(keyword)
            at += len(parts)
        else:
            tokens.append(words[at])
            at += 1
    return tokens


def _contexts(words: list[str], keyword: str, context_words: int) -> list[str]:
    """The context of each occurrence of *keyword*: half the words before it, the keyword and the rest after."""
    half = round(context_words / 2)
    tokens = _tokens(words, keyword)
    return [" ".join(tokens[max(0, at - half):at + half]) for at, token in enumerate(tokens) if token == keyword]


def _autopct(values):
    total = sum(values)
    return lambda pct: f"{pct:.2f}% ({int(round(pct * total / 100.0)):d})"


def _chart_data(counts: dict) -> tuple[list, list]:
    """Counts and labels of the keywords that were found, smallest first (for readability)."""
    found = sorted(((k, n) for k, n in counts.items() if n), key=lambda kv: (kv[1], kv[0]))
    return [n for _k, n in found], [k for k, _n in found]


def _save_nothing_found(path, title):
    """A chart saying no keyword was found (matplotlib cannot draw an empty pie)."""
    fig = Figure()
    ax = fig.subplots()
    ax.text(0.5, 0.5, "No keywords found", ha="center", va="center")
    ax.set_title(title)
    ax.axis("off")
    fig.savefig(path, bbox_inches="tight")


def _save_pie(path, counts, labels, title):
    if not counts:
        return _save_nothing_found(path, title)
    fig = Figure()
    ax = fig.subplots()
    ax.pie(counts, labels=labels, autopct=_autopct(counts), radius=2.0)
    ax.set_title(title)
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")


def _save_bar(path, counts, labels, title, xlabel):
    if not counts:
        return _save_nothing_found(path, title)
    fig = Figure()
    ax = fig.subplots()
    y_pos = list(range(len(labels)))
    ax.barh(y_pos, counts, align="center", alpha=0.5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Words")
    ax.set_title(title)
    ax.set_yticks(y_pos, labels)
    fig.savefig(path, bbox_inches="tight")


def _save_charts(pie: str, bar: str, counts: dict, title: str, xlabel: str):
    """A pie chart and a bar chart of *counts*."""
    values, labels = _chart_data(counts)
    _save_pie(pie, values, labels, title)
    _save_bar(bar, values, labels, title, xlabel)


def _append_rows(path: str, rows):
    with open(path, "a", encoding=CSV_ENCODING, newline="") as f:
        csv.writer(f).writerows(rows)


def _write_new_csv(path: str, header):
    with open(path, "w", encoding=CSV_ENCODING, newline="") as f:
        csv.writer(f).writerow(header)


def search_directory(input_dir, output_dir, keywords="", keyword_file="", filters="", filter_file="",
                     basic=False, context_words=5, on_progress=None, cancel=None):
    """Count *keywords* in every PDF under *input_dir*; write CSVs and charts to *output_dir*.

    keywords / filters: one per line, or read from *keyword_file* /
    *filter_file* when given (ValueError if there is no keyword).  *basic*
    applies basic_filter() instead of the filters.  Each hit's context is
    *context_words* words around it.

    on_progress(done, total, current_file) is called before each PDF; a set
    *cancel* event stops before the next one.  Returns {"files": PDFs searched,
    "total": PDFs found, "hits": keyword occurrences found, "charts": [total
    chart paths], "skipped": [{"input": path relative to *input_dir*,
    "message": why}]}: PDFs that cannot be read or have no text.  PDFs are
    named by their path relative to *input_dir*.
    """
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"{input_dir} is not a valid directory.")
    log.debug("keyword search: context=%s basic=%s in=%s out=%s keyword_file=%s filter_file=%s",
              context_words, basic, input_dir, output_dir, keyword_file, filter_file)
    pdfs = find_files(input_dir, [".pdf"])
    keyword_list = _load_keywords(keywords, keyword_file)
    clean = _text_filter(basic, filters, filter_file)
    context_words = int(context_words)

    # Keywords can contain characters that are not allowed in Windows
    # filenames, so their CSVs get safe names.
    keyword_csv = {k: os.path.join(output_dir, name)
                   for k, name in unique_safe_filenames(keyword_list, ".csv").items()}
    for keyword, path in keyword_csv.items():
        _write_new_csv(path, ["Year", "Page", f"Context: {keyword}"])
    overview = os.path.join(output_dir, OVERVIEW_CSV)
    _write_new_csv(overview, ["Year", *keyword_list])

    totals = dict.fromkeys(keyword_list, 0)
    read, skipped = 0, []
    for i, path in enumerate(pdfs):
        if cancel is not None and cancel.is_set():
            break
        rel = os.path.relpath(path, input_dir)
        if on_progress:
            on_progress(i, len(pdfs), os.path.basename(path))
        log.info("keywords: %s", path)
        try:
            pages = extract_pages(path)
        except Exception as e:
            log.warning("keywords: cannot read %s: %s", path, e)
            skipped.append({"input": rel, "message": f"could not be read ({e})"})
            continue
        if not any(text.strip() for text in pages):
            skipped.append({"input": rel, "message": "no text (scanned PDF? run OCR first)"})
            continue
        read += 1

        counts = dict.fromkeys(keyword_list, 0)
        for page, text in enumerate(pages, start=1):
            text = clean(text).lower()
            words = {}   # split once per page for each way of treating hyphens
            for keyword in keyword_list:
                hyphens_separate = "-" not in keyword
                if hyphens_separate not in words:
                    words[hyphens_separate] = _split_words(text, hyphens_separate)
                contexts = _contexts(words[hyphens_separate], keyword, context_words)
                if contexts:
                    counts[keyword] += len(contexts)
                    totals[keyword] += len(contexts)
                    _append_rows(keyword_csv[keyword], [[rel, page, context] for context in contexts])

        _append_rows(overview, [[rel, *counts.values()]])
        chart = os.path.join(output_dir, rel)
        os.makedirs(os.path.dirname(chart), exist_ok=True)
        _save_charts(chart + "-PIE.png", chart + "-BAR.png", counts,
                     f"Count for PDF {rel}\nPage count (PDF): {len(pages)}", "Word Count")

    total_pie, total_bar = os.path.join(output_dir, "totalPie.png"), os.path.join(output_dir, "totalBar.png")
    _save_charts(total_pie, total_bar, totals, "Total word count for every PDF", "Total Word Count")
    hits = sum(totals.values())
    log.info("keywords: %d of %d PDF(s) searched, %d hit(s)", read, len(pdfs), hits)
    if on_progress:
        on_progress(read + len(skipped), len(pdfs), "")
    return {"files": read, "total": len(pdfs), "hits": hits, "charts": [total_bar, total_pie], "skipped": skipped}
