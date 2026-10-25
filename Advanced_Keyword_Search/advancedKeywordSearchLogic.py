"""Keyword search: count keywords in a folder of PDFs and collect their context.

Every PDF under the input folder, sub-folders included, is searched page by
page.  Keywords are plain text matched as whole words, ignoring case and
punctuation at the edges of words ("york." is "york"); a keyword of several
words matches them in sequence.  Hyphens separate words unless the keyword
contains one, so "mill race" also finds "mill-race".  The filters apply to the
keywords as to the text, and both are compared with accents stored as separate
marks joined to their letters (also the spacing accents in "caf\u00b4e", as LaTeX
PDFs extract "caf\u00e9") and with letters in compatibility forms written plainly:
ligatures spelled out (the "\ufb01" in "\ufb01eld" is "fi"), Arabic presentation
forms as the base letters, fullwidth "\uff21" as "A".  Keywords that compare
alike ("york" and "york.") are searched once, and the summary says which were
counted together.  Every occurrence is counted once and gets one row in the
keyword's CSV.
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
import contextlib
import os
import re
import unicodedata

from matplotlib.figure import Figure

from common.paths import find_files, unique_safe_filenames, unreadable_entries
from common.pdf_text import extract_pages
from common.spreadsheet import safe_row
from common.text_files import read_text

log = logging.getLogger(__name__)

# CSVs are opened by researchers in Excel: UTF-8 with a BOM so non-Latin text
# displays correctly, and newline="" so the csv module controls line endings
# (otherwise Windows gets a blank line after every row).  Cells that Excel would
# take for a formula ("-5 degrees") get a leading apostrophe (common.spreadsheet).
CSV_ENCODING = "utf-8-sig"
OVERVIEW_CSV = "Data_Overview.csv"


def basic_filter(text: str) -> str:
    """Keep letters of any script (with their accents, also as combining marks),
    digits, hyphens and whitespace; drop other punctuation, symbols and OCR noise.

    Hyphens are kept so that "mill-race" stays two words (and matches a
    hyphenated keyword) instead of becoming "millrace".
    """
    return "".join(ch for ch in text if ch.isspace() or ch == "-" or unicodedata.category(ch)[0] in "LMN")


def _read_file(path: str, what: str) -> str:
    try:
        return read_text(path)
    except (OSError, ValueError) as e:
        raise ValueError(f"Cannot read the {what} file: {e}") from e


def _load_keywords(keywords: str, keyword_file: str) -> list[str]:
    """The keywords: one per line of the file if given, else of *keywords*.

    Surrounding and repeated spaces are removed and blank lines left out.
    """
    text = _read_file(keyword_file, "keyword") if keyword_file else keywords
    found = [k for k in (" ".join(line.split()) for line in text.splitlines()) if k]
    if not found:
        raise ValueError("No keywords to search for: enter one per line" +
                         (" in the keyword file." if keyword_file else "."))
    return found


def _text_filter(basic: bool, filters: str, filter_file: str):
    """A function removing the characters the user filters out of a page's text."""
    if basic:
        return basic_filter
    lines = _read_file(filter_file, "filter").replace("\r", "") if filter_file else filters
    # In NFC form like the text, so an "\u00e9" typed as e and a separate accent removes "\u00e9", not every "e".
    remove = "".join(unicodedata.normalize("NFC", line) for line in lines.split("\n"))
    table = str.maketrans("", "", remove)
    return lambda text: text.translate(table)


# Letters and digits in compatibility forms, written plainly ("\ufb01" -> "fi", Arabic presentation forms
# -> the base letters, fullwidth "\uff21" -> "A").  Not full NFKC: that also rewrites symbols people filter
# out ("\u2122" -> "TM", "\u00b2" -> "2") and splits a spacing accent into a space and a mark.
_COMPAT = {c: unicodedata.normalize("NFKC", chr(c)) for c in range(0x20000)
           if unicodedata.decomposition(chr(c)).startswith("<")
           and unicodedata.category(chr(c)) in {"Lu", "Ll", "Lt", "Lm", "Lo", "Nd"}}

# Spacing accents ("\u00b4" for U+0301) and their combining marks: LaTeX PDFs extract "caf\u00e9" as "caf\u00b4e".
_ACCENTS = {chr(c): nfkd[1:] for c in range(0x2000) for nfkd in [unicodedata.normalize("NFKD", chr(c))]
            if len(nfkd) > 1 and nfkd[0] == " " and all(unicodedata.category(m) == "Mn" for m in nfkd[1:])}
_ACCENTS.update({"\u02c6": "\u0302", "\u02c7": "\u030c"})   # circumflex and caron have no decomposition
_SPACING_ACCENT = re.compile(f"([{re.escape(''.join(_ACCENTS))}])([^\\W\\d_])")


def _join_accent(m) -> str:
    """A spacing accent and the letter after it as one letter ("\u00b4e" -> "\u00e9"), if there is one.

    "\u00b4" is also typed for an apostrophe ("it\u00b4s"), so it only joins a vowel.
    """
    accent, letter = m.groups()
    joined = unicodedata.normalize("NFC", letter + _ACCENTS[accent])
    if len(joined) == 1 and (accent != "\u00b4" or letter in "aeiouyAEIOUY"):
        return joined
    return m.group()


def _normalize(text: str) -> str:
    """*text* in NFC form, so with accents joined to their letters, also the spacing accents before them."""
    return unicodedata.normalize("NFC", _SPACING_ACCENT.sub(_join_accent, text))


def _comparable(text: str, clean) -> str:
    """*text* as compared with the keywords: normalized, filtered (*clean*), compatibility forms written plainly
    (see _COMPAT) and lower-cased.

    The filter runs before the compatibility forms are rewritten, so that it
    removes the characters it lists as written ("\ufb01"), and after, so that a
    letter it lists is removed where a ligature spelled it out too.
    """
    return clean(unicodedata.normalize("NFC", clean(_normalize(text)).translate(_COMPAT))).lower()


def _bare(word: str) -> str:
    """*word* without the punctuation at its edges ("(york)." -> "york"), or as is if that leaves nothing."""
    start, end = 0, len(word)
    while start < end and unicodedata.category(word[start])[0] == "P":
        start += 1
    while end > start and unicodedata.category(word[end - 1])[0] == "P":
        end -= 1
    return word[start:end] or word


_WORDS = {True: re.compile(r"[^-\s]+"), False: re.compile(r"\S+")}   # by whether hyphens separate words


def _words(text: str, hyphens_separate: bool) -> list[tuple[int, int, str]]:
    """The words of *text*: where each starts and ends, and the word as compared with keywords (see _bare)."""
    return [(m.start(), m.end(), _bare(m.group())) for m in _WORDS[hyphens_separate].finditer(text)]


def _keywords(lines: list[str], clean) -> tuple[dict[str, tuple[list[str], bool]], list[str]]:
    """Each keyword, lower-cased, and how it is compared: its words, and whether hyphens separate words.

    A keyword is filtered like the text (*clean*), so with the basic filter
    "o'brien" is compared as "obrien".  Of keywords compared alike only the
    first is kept, so no match is counted twice; one the filter empties is
    kept (once) but never found.  Also returns a note for each of these keywords.
    """
    found, kept, notes = {}, {}, []
    for line in lines:
        compared = _comparable(line, clean)
        hyphens_separate = "-" not in compared
        parts = [bare for _start, _end, bare in _words(compared, hyphens_separate)]
        keyword = line.lower()
        # Keywords the filter empties all compare as no words, so they are told apart by name.
        key = (tuple(parts), hyphens_separate) if parts else keyword
        if key in kept:
            if kept[key] != keyword:
                notes.append(f'"{keyword}" was counted as "{kept[key]}": they match the same words.')
            continue
        n = 2
        while keyword in found:   # "York" and "york" only differ with a filter that removes capitals
            keyword, n = f"{line.lower()} ({n})", n + 1
        if not parts:
            notes.append(f'"{keyword}" was not searched: the filter leaves nothing of it.')
        kept[key] = keyword
        found[keyword] = parts, hyphens_separate
    return found, notes


def _index(words: list) -> dict[str, list[int]]:
    """Where each word occurs in *words* (see _words), by the word as compared with keywords."""
    index = {}
    for at, (_start, _end, bare) in enumerate(words):
        index.setdefault(bare, []).append(at)
    return index


def _occurrences(words: list, index: dict, parts: list[str]) -> list[int]:
    """Where each occurrence of the words *parts* starts in *words*, found through *index* (word -> positions).

    Occurrences do not overlap: "the the" occurs once in "the the the".
    """
    starts, free = [], 0
    for at in index.get(parts[0], ()) if parts else ():
        if at >= free and [bare for _start, _end, bare in words[at:at + len(parts)]] == parts:
            starts.append(at)
            free = at + len(parts)
    return starts


def _contexts(text: str, words: list, starts: list[int], length: int, context_words: int) -> list[str]:
    """The context of each occurrence of a keyword of *length* words, starting at the positions *starts*.

    A context is *context_words* words, the keyword included, and another
    occurrence of a keyword of several words counts as one: as many before it
    as after, and one more before when the number is even.  It is *text* as
    written from the first of these words to the last, with a minus sign
    before the first ("-5") and a hyphen ending the last ("mill-" at the end of
    a line); line breaks and runs of spaces become one space.  Words that
    continue on the next page are not joined.
    """
    before = context_words // 2
    after = max(context_words - before - 1, 0)
    is_start = set(starts)
    found = []
    for at in starts:
        first, end = at, at + length
        for _ in range(before):
            if first == 0:
                break
            first -= length if first - length in is_start else 1
        for _ in range(after):
            if end == len(words):
                break
            end += length if end in is_start else 1
        start, stop = words[first][0], words[end - 1][1]
        edge = start
        while edge > 0 and text[edge - 1] == "-":
            edge -= 1
        if edge == 0 or text[edge - 1].isspace():
            start = edge
        edge = stop
        while edge < len(text) and text[edge] == "-":
            edge += 1
        if edge == len(text) or text[edge].isspace():
            stop = edge
        found.append(" ".join(text[start:stop].split()))
    return found


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


def _plain(text: str) -> str:
    """*text* shown as written: matplotlib reads text between two "$" as mathematics."""
    return text.replace("$", r"\$")


def _save_charts(pie: str, bar: str, counts: dict, title: str, xlabel: str) -> dict[str, str]:
    """A pie chart and a bar chart of *counts*; why each chart that could not be saved was not, by its path.

    A path too long for Windows, say, loses a chart, not the search.  A chart
    that is not saved leaves no file at its path, so none from an earlier search.
    """
    values, labels = _chart_data(counts)
    labels, title = [_plain(label) for label in labels], _plain(title)
    failed = {}
    for path, save, extra in ((pie, _save_pie, ()), (bar, _save_bar, (xlabel,))):
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            save(path, values, labels, title, *extra)
        except Exception as e:   # OSError for the path; matplotlib raises ValueError, OverflowError and others
            log.warning("keywords: cannot save %s: %s", path, e)
            failed[path] = str(e)
            with contextlib.suppress(OSError):
                if os.path.isfile(path):
                    os.remove(path)
    return failed


def _append_rows(path: str, rows):
    with open(path, "a", encoding=CSV_ENCODING, newline="") as f:
        csv.writer(f).writerows(safe_row(row) for row in rows)


def _write_new_csv(path: str, header):
    with open(path, "w", encoding=CSV_ENCODING, newline="") as f:
        csv.writer(f).writerow(safe_row(header))


def search_directory(input_dir, output_dir, keywords="", keyword_file="", filters="", filter_file="",
                     basic=False, context_words=5, on_progress=None, cancel=None):
    """Count *keywords* in every PDF under *input_dir*; write CSVs and charts to *output_dir*.

    keywords / filters: one per line, or read from *keyword_file* /
    *filter_file* when given (ValueError if there is no keyword).  *basic*
    applies basic_filter() instead of the filters.  Each hit's context is
    *context_words* words, the keyword included (see _contexts).

    on_progress(done, total, current_file) is called before each PDF; a set
    *cancel* event stops before the next one.  Returns {"files": PDFs searched,
    "total": PDFs found, "hits": keyword occurrences found, "charts": [total
    chart paths saved], "skipped": [{"input": path relative to *input_dir*,
    "message": why}]: PDFs not searched, because they cannot be read or have no
    text, "warnings": [the same]: PDFs searched (and counted) whose charts
    cannot be saved, "keyword_notes": [keywords counted with another or not
    searched (see _keywords)]}.  PDFs are named by their path relative to
    *input_dir*.
    """
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"{input_dir} is not a valid directory.")
    log.debug("keyword search: context=%s basic=%s in=%s out=%s keyword_file=%s filter_file=%s",
              context_words, basic, input_dir, output_dir, keyword_file, filter_file)
    unreadable = []
    pdfs = find_files(input_dir, [".pdf"], unreadable=unreadable)
    clean = _text_filter(basic, filters, filter_file)
    compared, keyword_notes = _keywords(_load_keywords(keywords, keyword_file), clean)
    keyword_list = list(compared)
    context_words = int(context_words)

    # Keywords can contain characters that are not allowed in Windows
    # filenames, so their CSVs get safe names.
    keyword_csv = {k: os.path.join(output_dir, name)
                   for k, name in unique_safe_filenames(keyword_list, ".csv", reserved=[OVERVIEW_CSV]).items()}
    for keyword, path in keyword_csv.items():
        _write_new_csv(path, ["Year", "Page", f"Context: {keyword}"])
    overview = os.path.join(output_dir, OVERVIEW_CSV)
    _write_new_csv(overview, ["Year", *keyword_list])

    totals = dict.fromkeys(keyword_list, 0)
    modes = {hyphens_separate for _parts, hyphens_separate in compared.values()}
    read, done, skipped, warnings = 0, 0, unreadable_entries(unreadable, input_dir), []
    for i, path in enumerate(pdfs):
        if cancel is not None and cancel.is_set():
            break
        done = i + 1
        rel = os.path.relpath(path, input_dir)
        if on_progress:
            on_progress(i, len(pdfs), rel)
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
            text = _comparable(text, clean)
            # For each way of treating hyphens: the page's words and where each occurs.
            split = {mode: (words, _index(words)) for mode in modes for words in [_words(text, mode)]}
            for keyword, (parts, hyphens_separate) in compared.items():
                words, index = split[hyphens_separate]
                starts = _occurrences(words, index, parts)
                if starts:
                    contexts = _contexts(text, words, starts, len(parts), context_words)
                    counts[keyword] += len(contexts)
                    totals[keyword] += len(contexts)
                    _append_rows(keyword_csv[keyword], [[rel, page, context] for context in contexts])

        _append_rows(overview, [[rel, *counts.values()]])
        pie, bar = os.path.join(output_dir, rel + "-PIE.png"), os.path.join(output_dir, rel + "-BAR.png")
        failed = _save_charts(pie, bar, counts, f"Count for PDF {rel}\nPage count (PDF): {len(pages)}", "Word Count")
        if failed:
            which = "charts" if len(failed) == 2 else "pie chart" if pie in failed else "bar chart"
            why = "; ".join(dict.fromkeys(failed.values()))   # once when both fail alike
            warnings.append({"input": rel, "message": f"searched, but its {which} could not be saved ({why})"})

    total_pie, total_bar = os.path.join(output_dir, "totalPie.png"), os.path.join(output_dir, "totalBar.png")
    failed = _save_charts(total_pie, total_bar, totals, "Total word count for every PDF", "Total Word Count")
    charts = [chart for chart in (total_bar, total_pie) if chart not in failed]
    warnings += [{"input": os.path.basename(chart), "message": f"could not be saved ({why})"}
                 for chart, why in failed.items()]
    hits = sum(totals.values())
    log.info("keywords: %d of %d PDF(s) searched, %d hit(s)", read, len(pdfs), hits)
    if on_progress:
        on_progress(done, len(pdfs), "")
    return {"files": read, "total": len(pdfs), "hits": hits, "charts": charts, "skipped": skipped,
            "warnings": warnings, "keyword_notes": keyword_notes}
