"""Token-aware recursive text splitting for RAG.

Sizes are measured in the embedding model's own tokens.  Defaults: chunks of at
most 256 tokens with ~32 tokens of overlap.  multilingual-e5-small reads at most
512 tokens (including its "passage: " prefix and special tokens), and the
reranker sees query + passage within its own 512-token limit, so 256-token
chunks fit both with room to spare while keeping citations specific.

Splitting prefers paragraph breaks, then sentence boundaries
(NLP.text_utils), then whitespace for a single over-long sentence, then
characters for a run without spaces longer than a chunk (unpunctuated
Chinese, a URL).  Overlap is made of whole trailing units (sentences) of the
previous chunk.
"""
import re
from dataclasses import dataclass

from NLP.text_utils import sentence_spans

MAX_TOKENS = 256
OVERLAP_TOKENS = 32


@dataclass(frozen=True)
class Chunk:
    text: str
    file: str            # path relative to the corpus folder
    page: int | None     # 1-based page (PDFs)
    start: int           # character offsets into the page/section text
    end: int
    ordinal: int         # position of the chunk within its file


def _pieces(text: str, start: int, end: int, count_tokens, max_tokens: int):
    """(start, end, tokens) of consecutive pieces of text[start:end], each as long as fits *max_tokens*."""
    pieces = []
    while start < end:
        low, high = start + 1, end   # the longest piece that fits; one character always goes
        while low < high:
            mid = (low + high + 1) // 2
            if count_tokens(text[start:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1
        pieces.append((start, low, count_tokens(text[start:low])))
        start = low
    return pieces


def _units(text: str, count_tokens, max_tokens: int):
    """(start, end, tokens) of sentences in paragraph order, words for long ones, and pieces of long words."""
    units = []
    for para in re.finditer(r"\S(?:.*?\S)?(?=\s*\n\s*\n|\s*$)", text, re.S):
        p_start = para.start()
        for s, e in sentence_spans(para.group()):
            s, e = p_start + s, p_start + e
            n = count_tokens(text[s:e])
            if n <= max_tokens:
                units.append((s, e, n))
                continue
            # A sentence longer than a chunk: fall back to groups of words.
            words = [(m.start() + s, m.end() + s) for m in re.finditer(r"\S+", text[s:e])]
            group = []
            for w in words:
                if count_tokens(text[w[0]:w[1]]) > max_tokens:
                    if group:
                        units.append((group[0][0], group[-1][1], count_tokens(text[group[0][0]:group[-1][1]])))
                        group = []
                    units.extend(_pieces(text, w[0], w[1], count_tokens, max_tokens))
                    continue
                candidate = group + [w]
                if group and count_tokens(text[candidate[0][0]:candidate[-1][1]]) > max_tokens:
                    units.append((group[0][0], group[-1][1], count_tokens(text[group[0][0]:group[-1][1]])))
                    group = [w]
                else:
                    group = candidate
            if group:
                units.append((group[0][0], group[-1][1], count_tokens(text[group[0][0]:group[-1][1]])))
    return units


def split_text(text: str, count_tokens, max_tokens: int = MAX_TOKENS,
               overlap_tokens: int = OVERLAP_TOKENS) -> list[tuple[int, int]]:
    """Chunk boundaries as (start, end) character offsets into *text*."""
    units = _units(text, count_tokens, max_tokens)
    spans, current, total = [], [], 0
    for unit in units:
        if current and total + unit[2] > max_tokens:
            spans.append((current[0][0], current[-1][1]))
            # Carry whole trailing units into the next chunk as overlap.
            carry, carried = [], 0
            for prev in reversed(current):
                if carried + prev[2] > overlap_tokens or carried + prev[2] + unit[2] > max_tokens:
                    break
                carry.insert(0, prev)
                carried += prev[2]
            current, total = carry, carried
        current.append(unit)
        total += unit[2]
    if current:
        spans.append((current[0][0], current[-1][1]))
    return spans


def chunk_document(rel_path: str, sections, count_tokens, max_tokens: int = MAX_TOKENS,
                   overlap_tokens: int = OVERLAP_TOKENS) -> list[Chunk]:
    """Chunks for every section (page) of one document."""
    chunks = []
    for section in sections:
        for start, end in split_text(section.text, count_tokens, max_tokens, overlap_tokens):
            chunks.append(Chunk(section.text[start:end], rel_path, section.page, start, end, len(chunks)))
    return chunks
