"""Small, dependency-free text utilities: word tokens, sentences, stopwords.

These replace NLTK's word_tokenize/sent_tokenize and stopword corpus.

Limitations (by design; no statistical models):
- Words are runs of Unicode letters, optionally joined by an apostrophe or
  hyphen ("miller's", "well-known").  Numbers are not words.
- Scripts written without spaces are not segmented into words: Chinese and
  Japanese (Han/kana) become one token per character; Thai, Lao, Khmer and
  Burmese stay as whole runs between spaces/punctuation.
- Sentence splitting is rule-based: it breaks after . ! ? and … followed by
  whitespace and a capital letter, digit or opening quote/bracket (or a
  letter from a script without case), after 。！？, and at blank lines.  It
  knows common abbreviations and single-letter initials, but unusual
  abbreviations followed by a capitalized name will be split.
"""
import functools
import json
import os
import re
import unicodedata

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stopwords")

# ---------------------------------------------------------------- words ----

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_CJK_CHAR = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿\U00020000-\U0002ffff]")


def word_spans(text: str) -> list[tuple[str, int, int]]:
    """Word tokens with character offsets: [(word, start, end), ...]."""
    spans = []
    for m in _WORD_RE.finditer(text):
        token, start = m.group(), m.start()
        if not _CJK_CHAR.search(token):
            spans.append((token, start, m.end()))
            continue
        # Han/kana: one token per character; other letters in the run stay together.
        run_start = None
        for i, ch in enumerate(token):
            if _CJK_CHAR.match(ch):
                if run_start is not None:
                    spans.append((token[run_start:i], start + run_start, start + i))
                    run_start = None
                spans.append((ch, start + i, start + i + 1))
            elif run_start is None:
                run_start = i
        if run_start is not None:
            spans.append((token[run_start:], start + run_start, m.end()))
    return spans


def words(text: str, lowercase: bool = True) -> list[str]:
    """Word tokens of *text* (lowercased by default)."""
    tokens = [w for w, _s, _e in word_spans(text)]
    return [t.lower() for t in tokens] if lowercase else tokens


# ------------------------------------------------------------ sentences ----

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "st", "sr", "jr", "rev", "hon", "gen", "col", "capt",
    "lt", "sgt", "mt", "ft", "no", "nos", "vol", "vols", "fig", "figs", "p", "pp", "ed", "eds",
    "etc", "e.g", "i.e", "cf", "vs", "viz", "ca", "c", "approx", "dept", "est", "inc", "ltd", "co",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mme", "mlle", "sig", "hr", "fr", "bd", "nr", "s", "art",
}
_OPENERS = "\"'“‘«„(["
_CLOSERS = "\"'”’»)]"
# Candidate end: terminators, optional closing quotes/brackets, then whitespace.
_WESTERN_END = re.compile(r"[.!?…]+[" + re.escape(_CLOSERS) + r"]*(?=\s)")
_CJK_END = re.compile(r"[。！？]+[」』）”’\"']*")
_PARAGRAPH = re.compile(r"\n[ \t]*\n\s*")


def _starts_sentence(ch: str) -> bool:
    if ch.isdigit() or ch in _OPENERS:
        return True
    if not ch.isalpha():
        return False
    # Upper case, or a letter from a script without case (Arabic, Hebrew, CJK...).
    return ch.isupper() or ch.lower() == ch.upper() and unicodedata.category(ch) == "Lo"


def _is_abbreviation(text: str, dot: int) -> bool:
    """True if the '.' at text[dot] ends an abbreviation or an initial."""
    m = re.search(r"([^\W\d_]+(?:\.[^\W\d_]+)*)$", text[:dot])
    if not m:
        return False
    token = m.group(1)
    if len(token) == 1 and token.isupper():
        return True  # an initial: "J. K. Nicholson"
    return token.lower() in _ABBREVIATIONS


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Sentence boundaries as (start, end) offsets, whitespace trimmed."""
    cuts = set()
    for m in _PARAGRAPH.finditer(text):
        cuts.add(m.start())
    for m in _CJK_END.finditer(text):
        cuts.add(m.end())
    for m in _WESTERN_END.finditer(text):
        rest = text[m.end():].lstrip()
        if not rest or not _starts_sentence(rest[0]):
            continue
        if text[m.start()] == "." and m.group().rstrip(_CLOSERS) == "." and _is_abbreviation(text, m.start()):
            continue
        cuts.add(m.end())

    spans, start = [], 0
    for cut in sorted(cuts) + [len(text)]:
        s, e = start, cut
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            spans.append((s, e))
        start = cut
    return spans


def sentences(text: str) -> list[str]:
    """Split *text* into sentences."""
    return [text[s:e] for s, e in sentence_spans(text)]


# ------------------------------------------------------------ stopwords ----

# Snowball stop lists (BSD-3-Clause): curated function words.
_SNOWBALL = {
    "da": ("Danish", "danish"), "nl": ("Dutch", "dutch"), "en": ("English", "english"),
    "fi": ("Finnish", "finnish"), "fr": ("French", "french"), "de": ("German", "german"),
    "hu": ("Hungarian", "hungarian"), "id": ("Indonesian", "indonesian"), "ga": ("Irish", "irish"),
    "it": ("Italian", "italian"), "no": ("Norwegian", "norwegian"), "pt": ("Portuguese", "portuguese"),
    "ru": ("Russian", "russian"), "st": ("Sesotho", "sesotho"), "es": ("Spanish", "spanish"),
    "sv": ("Swedish", "swedish"), "uk": ("Ukrainian", "ukrainian"),
}
# stopwords-iso (MIT compilation) for languages Snowball does not cover.  These
# lists are broader and can include content words.
_ISO_NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "br": "Breton",
    "ca": "Catalan", "cs": "Czech", "el": "Greek", "eo": "Esperanto", "et": "Estonian",
    "eu": "Basque", "fa": "Persian", "gl": "Galician", "gu": "Gujarati", "ha": "Hausa",
    "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "hy": "Armenian", "ja": "Japanese",
    "ko": "Korean", "ku": "Kurdish", "la": "Latin", "lt": "Lithuanian", "lv": "Latvian",
    "mr": "Marathi", "ms": "Malay", "pl": "Polish", "ro": "Romanian", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "sw": "Swahili", "th": "Thai", "tl": "Tagalog",
    "tr": "Turkish", "ur": "Urdu", "vi": "Vietnamese", "yo": "Yoruba", "zh": "Chinese", "zu": "Zulu",
}

# code -> (language name, source label), sorted by name for the UI.
STOPWORD_LANGUAGES = dict(sorted(
    {**{c: (n, "stopwords-iso (extended)") for c, n in _ISO_NAMES.items()},
     **{c: (n, "Snowball") for c, (n, _f) in _SNOWBALL.items()}}.items(),
    key=lambda kv: kv[1][0],
))


@functools.lru_cache(maxsize=None)
def _iso_lists() -> dict:
    with open(os.path.join(_DATA_DIR, "stopwords-iso.json"), encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def stopwords(code: str) -> frozenset:
    """Stopwords for an ISO 639-1 language code (KeyError if unavailable)."""
    if code in _SNOWBALL:
        path = os.path.join(_DATA_DIR, "snowball", _SNOWBALL[code][1] + ".txt")
        with open(path, encoding="utf-8") as f:
            # Snowball format: words at the start of lines, comments after '|'.
            return frozenset(w.lower() for line in f for w in line.split("|")[0].split())
    if code in _ISO_NAMES:
        return frozenset(w.lower() for w in _iso_lists()[code])
    raise KeyError(f"no stopword list for language {code!r}")


def parse_custom_stopwords(text: str) -> set[str]:
    """User-entered stopwords, separated by newlines, commas, semicolons or spaces."""
    return {w.lower() for w in re.split(r"[\s,;]+", text or "") if w}
