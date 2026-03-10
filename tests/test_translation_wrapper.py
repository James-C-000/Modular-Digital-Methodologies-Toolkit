from Translation.googletranslateWrapper import LANGUAGE_CODES


def test_language_codes_contains_english():
    assert "English" in LANGUAGE_CODES
    assert LANGUAGE_CODES["English"] == "en"


def test_language_codes_contains_spanish():
    assert "Spanish" in LANGUAGE_CODES
    assert LANGUAGE_CODES["Spanish"] == "es"


def test_language_codes_has_entries():
    assert len(LANGUAGE_CODES) >= 14
