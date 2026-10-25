import os
import zipfile

import pytest

from Translation import offline_translation as ot
from Translation.bpe import BPE


class TestIndex:
    def test_index_lists_argos_pairs_with_sizes(self):
        pairs = ot.index_pairs()
        assert ("fr", "en") in pairs and ("en", "es") in pairs
        assert all(p["url"].startswith("https://") and p["size"] > 1_000_000 for p in ot.load_index())

    def test_language_names(self):
        names = ot.language_names()
        assert names["fr"] == "French" and names["en"] == "English"


class TestRoute:
    AVAILABLE = {("fr", "en"), ("en", "de"), ("es", "pt")}

    def test_direct(self):
        assert ot.route("es", "pt", available=self.AVAILABLE) == [("es", "pt")]

    def test_pivot_through_english(self):
        assert ot.route("fr", "de", available=self.AVAILABLE) == [("fr", "en"), ("en", "de")]

    def test_missing(self):
        assert ot.route("de", "fr", available=self.AVAILABLE) is None
        assert ot.route("fr", "fr", available=self.AVAILABLE) == []


def test_paragraphs_rejoin_wrapped_lines_but_keep_sentence_lines():
    text = "The mayor read the\ndecree aloud.\nThe crowd\nlistened.\n\nA new paragraph"
    assert ot._paragraphs(text) == ["The mayor read the decree aloud.", "The crowd listened.", "A new paragraph"]


def test_package_extraction_refuses_path_traversal(tmp_path):
    bad = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../outside.txt", "x")
    with zipfile.ZipFile(bad) as z, pytest.raises(ValueError):
        ot._safe_extract(z, str(tmp_path / "out"))
    assert not (tmp_path / "outside.txt").exists()


def test_detect_language_respects_candidates():
    text = "Le notaire a rédigé l'acte de vente en présence des deux témoins soussignés."
    assert ot.detect_language(text) == "fr"
    assert ot.detect_language(text, candidates={"fr", "de"}) == "fr"
    assert ot.detect_language("O capitão mandou registar a chegada da nau.", candidates={"pb"}) == "pb"


def test_bpe_small_codes():
    bpe = BPE("#version: 0.2\nl o\nlo w</w>\ne r</w>\n")
    assert bpe.segment_tokens(["low", "lower", "newer"]) == ["low", "lo@@", "w@@", "er", "n@@", "e@@", "w@@", "er"]


class _Upper:
    def translate(self, sentences):
        return [s.upper() for s in sentences]

    def count_tokens(self, text):
        return len(text.split())


def test_translate_directory_with_a_stub_model(tmp_path, monkeypatch):
    monkeypatch.setattr(ot, "installed_pairs", lambda models_root=None: {("fr", "en")})
    monkeypatch.setattr(ot, "get_translator", lambda a, b, models_root=None: _Upper())
    (tmp_path / "lettre.txt").write_text("Le notaire a rédigé l'acte. Les témoins ont signé.", encoding="utf-8")
    (tmp_path / "lettre_translated.txt").write_text("previous output", encoding="utf-8")
    (tmp_path / "vide.txt").write_text("   ", encoding="utf-8")
    results = {os.path.basename(r["input"]): r for r in ot.translate_directory(str(tmp_path), None, "en")}
    assert set(results) == {"lettre.txt", "vide.txt"}  # outputs are not re-translated
    assert results["lettre.txt"]["status"] == "success" and results["lettre.txt"]["language"] == "fr"
    out = (tmp_path / "lettre_translated.txt").read_text(encoding="utf-8")
    assert out == "LE NOTAIRE A RÉDIGÉ L'ACTE. LES TÉMOINS ONT SIGNÉ."
    assert results["vide.txt"]["status"] == "skipped"


def test_translate_directory_reads_legacy_encoded_text(tmp_path, monkeypatch):
    monkeypatch.setattr(ot, "installed_pairs", lambda models_root=None: {("fr", "en")})
    monkeypatch.setattr(ot, "get_translator", lambda a, b, models_root=None: _Upper())
    (tmp_path / "lettre.txt").write_bytes("Le notaire a rédigé l'acte.".encode("cp1252"))
    [result] = ot.translate_directory(str(tmp_path), "fr", "en")
    assert result["status"] == "success", result
    assert (tmp_path / "lettre_translated.txt").read_text(encoding="utf-8") == "LE NOTAIRE A RÉDIGÉ L'ACTE."


def test_long_sentences_are_split_for_the_model():
    long_sentence = " ".join(["mot"] * 450)
    pieces = ot._chunks_for(_Upper(), long_sentence)
    assert len(pieces) == 3 and all(len(p.split()) <= ot.MAX_TOKENS for p in pieces)


network = pytest.mark.skipif(not os.environ.get("MDMT_NETWORK_TESTS"),
                             reason="downloads Argos packages; set MDMT_NETWORK_TESTS=1")


@pytest.fixture(scope="module")
def models_root(tmp_path_factory):
    return str(tmp_path_factory.mktemp("models"))


@network
def test_sentencepiece_package(models_root):
    ot.download_package("fr", "en", models_root)
    assert ("fr", "en") in ot.installed_pairs(models_root)
    out = ot.translate_text("Le chat dort sur la chaise. Il fait beau aujourd'hui.", "fr", "en", models_root)
    assert "cat" in out.lower() and "today" in out.lower()


@network
def test_bpe_package_and_pivot(models_root):
    ot.download_package("en", "pl", models_root)
    out = ot.translate_text("The cat is sleeping on the chair.", "en", "pl", models_root)
    assert "kot" in out.lower()
    # fr -> pl has no direct package: pivots through English.
    assert ot.route("fr", "pl", models_root) == [("fr", "en"), ("en", "pl")]
    assert "kot" in ot.translate_text("Le chat dort sur la chaise.", "fr", "pl", models_root).lower()
