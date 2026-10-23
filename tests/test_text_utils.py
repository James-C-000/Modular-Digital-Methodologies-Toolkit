import pytest

from NLP.text_utils import (
    STOPWORD_LANGUAGES,
    parse_custom_stopwords,
    sentence_spans,
    sentences,
    stopwords,
    word_spans,
    words,
)


class TestWords:
    def test_unicode_letters_apostrophes_and_hyphens(self):
        assert words("L'État, the miller's well-known Café — naïve 1743!") == [
            "l'état", "the", "miller's", "well-known", "café", "naïve"]

    def test_case_is_kept_when_asked(self):
        assert words("Ada Lovelace", lowercase=False) == ["Ada", "Lovelace"]

    def test_numbers_and_punctuation_are_not_words(self):
        assert words("12 3.5 -- ... ___") == []

    def test_cyrillic_greek_arabic(self):
        assert words("Москва γράμμα القاهرة") == ["москва", "γράμμα", "القاهرة"]

    def test_cjk_is_split_into_characters(self):
        # No spaces between words: character tokens (documented limitation).
        assert words("知府下令") == ["知", "府", "下", "令"]
        assert words("Tokyo東京") == ["tokyo", "東", "京"]

    def test_spans_point_into_the_text(self):
        text = "  Ada met Babbage."
        assert [(w, text[s:e]) for w, s, e in word_spans(text)] == [
            ("Ada", "Ada"), ("met", "met"), ("Babbage", "Babbage")]


class TestSentences:
    @pytest.mark.parametrize("text,expected", [
        ("It rained. The mill flooded.", ["It rained.", "The mill flooded."]),
        ("Mr. Smith met Dr. Jones in St. Ives.", ["Mr. Smith met Dr. Jones in St. Ives."]),
        ("J. K. Nicholson wrote it. It sold well.", ["J. K. Nicholson wrote it.", "It sold well."]),
        ("It cost 3.5 florins. He paid.", ["It cost 3.5 florins.", "He paid."]),
        ('He said "Stop!" Then he left.', ['He said "Stop!"', "Then he left."]),
        ("Wait... what happened? Nobody knew.", ["Wait... what happened?", "Nobody knew."]),
        ("Grain, wool, etc. were taxed.", ["Grain, wool, etc. were taxed."]),
        ("知府下令修缮城墙。工程于秋天完成！", ["知府下令修缮城墙。", "工程于秋天完成！"]),
        ("First paragraph without a stop\n\nSecond paragraph", ["First paragraph without a stop", "Second paragraph"]),
        ("Губернатор приказал. Опись составлена.", ["Губернатор приказал.", "Опись составлена."]),
        ("", []),
    ])
    def test_split(self, text, expected):
        assert sentences(text) == expected

    def test_spans_cover_the_sentences(self):
        text = "One. Two."
        assert [text[s:e] for s, e in sentence_spans(text)] == ["One.", "Two."]


class TestStopwords:
    def test_english_uses_snowball_function_words(self):
        en = stopwords("en")
        assert {"the", "and", "of", "which"} <= en
        assert not {"computer", "information", "research", "world"} & en
        assert STOPWORD_LANGUAGES["en"][1] == "Snowball"

    def test_languages_without_snowball_fall_back_to_stopwords_iso(self):
        la = stopwords("la")
        assert {"et", "atque", "autem"} <= la
        assert STOPWORD_LANGUAGES["la"] == ("Latin", "stopwords-iso (extended)")

    def test_every_listed_language_loads(self):
        assert len(STOPWORD_LANGUAGES) >= 58
        for code in STOPWORD_LANGUAGES:
            assert stopwords(code), code

    def test_unknown_language(self):
        with pytest.raises(KeyError):
            stopwords("xx")

    def test_custom_stopwords(self):
        assert parse_custom_stopwords("Mill, river\nThe  parish;;") == {"mill", "river", "the", "parish"}
