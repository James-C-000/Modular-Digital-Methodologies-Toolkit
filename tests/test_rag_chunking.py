from RAG.chunking import chunk_document, split_text
from RAG.loaders import Section


def words(text):  # token counter stand-in: one token per whitespace word
    return len(text.split())


TEXT = ("The mill flooded in 1751. The bridge was carried away. " * 12
        + "\n\nA new paragraph about the harvest of 1752. Grain prices fell. " * 6)


def test_chunks_respect_the_token_budget_and_cover_the_text():
    spans = split_text(TEXT, words, max_tokens=40, overlap_tokens=8)
    assert len(spans) > 3
    assert all(words(TEXT[s:e]) <= 40 for s, e in spans)
    covered = set()
    for s, e in spans:
        covered.update(range(s, e))
    letters = {i for i, ch in enumerate(TEXT) if not ch.isspace()}
    assert letters <= covered


def test_consecutive_chunks_overlap_by_whole_sentences():
    spans = split_text(TEXT, words, max_tokens=40, overlap_tokens=8)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert s2 < e1, "expected overlap"
        assert TEXT[s2:e1].strip()[0].isupper()  # overlap starts at a sentence


def test_chunks_prefer_paragraph_and_sentence_boundaries():
    spans = split_text(TEXT, words, max_tokens=40, overlap_tokens=0)
    for s, e in spans:
        assert TEXT[e - 1] in ".\n" or e == len(TEXT.rstrip())


def test_an_overlong_sentence_is_split_at_words():
    sentence = "word " * 100
    spans = split_text(sentence, words, max_tokens=30, overlap_tokens=0)
    assert len(spans) == 4 and all(words(sentence[s:e]) <= 30 for s, e in spans)


def test_short_text_is_one_chunk_and_empty_text_none():
    assert split_text("A single short note.", words, 40, 8) == [(0, 20)]
    assert split_text("   \n  ", words, 40, 8) == []


def test_chunk_metadata_points_back_into_the_source():
    sections = [Section("First page. It talks about the mill.", page=1),
                Section("Second page mentions the bridge.", page=2)]
    chunks = chunk_document("ledger.pdf", sections, words, max_tokens=40, overlap_tokens=0)
    assert [(c.file, c.page, c.ordinal) for c in chunks] == [("ledger.pdf", 1, 0), ("ledger.pdf", 2, 1)]
    for c, section in zip(chunks, sections):
        assert section.text[c.start:c.end] == c.text
