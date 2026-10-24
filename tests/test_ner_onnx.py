"""NER on ONNX Runtime: aggregation and windowing (no model download needed),
plus model-backed checks that run with MDMT_NETWORK_TESTS=1."""
import json
import os

import numpy as np
import pytest

from NLP import ner_onnx
from NLP.ner_onnx import aggregate_simple, window_starts

LABELS = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC"]


def _logits(tags):
    out = np.full((len(tags), len(LABELS)), -5.0, dtype=np.float32)
    for i, t in enumerate(tags):
        out[i, LABELS.index(t)] = 5.0
    return out


class TestAggregation:
    TEXT = "Ada Lovelace met Babbage in London ."
    #       tokens: Ada | Love | ##lace | met | Bab | ##bage | in | London | .
    OFFSETS = [(0, 3), (4, 8), (8, 12), (13, 16), (17, 20), (20, 24), (25, 27), (28, 34), (35, 36)]

    def test_groups_b_and_i_tokens_into_entities_with_offsets(self):
        tags = ["B-PER", "I-PER", "I-PER", "O", "B-PER", "I-PER", "O", "B-LOC", "O"]
        ents = aggregate_simple(self.TEXT, self.OFFSETS, _logits(tags), LABELS)
        assert [(e["entity_group"], e["word"], e["start"], e["end"]) for e in ents] == [
            ("PER", "Ada Lovelace", 0, 12), ("PER", "Babbage", 17, 24), ("LOC", "London", 28, 34)]
        assert all(0.9 < e["score"] <= 1.0 for e in ents)

    def test_b_tag_starts_a_new_entity_of_the_same_type(self):
        tags = ["B-PER", "I-PER", "I-PER", "O", "B-PER", "B-PER", "O", "O", "O"]
        ents = aggregate_simple(self.TEXT, self.OFFSETS, _logits(tags), LABELS)
        assert [e["word"] for e in ents] == ["Ada Lovelace", "Bab", "bage"]

    def test_type_change_without_b_tag_still_splits(self):
        tags = ["B-PER", "I-ORG", "O", "O", "O", "O", "O", "I-LOC", "O"]
        ents = aggregate_simple(self.TEXT, self.OFFSETS, _logits(tags), LABELS)
        assert [(e["entity_group"], e["word"]) for e in ents] == [("PER", "Ada"), ("ORG", "Love"), ("LOC", "London")]


class TestWindows:
    def test_short_input_is_one_window(self):
        assert window_starts(100, size=510, stride=382) == [0]

    def test_windows_overlap_and_cover_the_end(self):
        starts = window_starts(1200, size=510, stride=382)
        assert starts[0] == 0 and starts[-1] + 510 >= 1200
        assert all(b - a == 382 for a, b in zip(starts, starts[1:-1]))

    def test_each_token_uses_the_window_where_it_is_most_central(self):
        best = ner_onnx.best_window_for_tokens(1200, window_starts(1200, 510, 382), 510)
        assert best[0] == 0 and best[1199] == window_starts(1200, 510, 382)[-1]
        # token 450 is 60 from window 0's right edge but 68 into window 1
        assert best[450] == 382


network = pytest.mark.skipif(not os.environ.get("MDMT_NETWORK_TESTS"),
                             reason="downloads the NER model; set MDMT_NETWORK_TESTS=1")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "ner_sample.txt")


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    return ner_onnx.load_model(models_root=str(tmp_path_factory.mktemp("models")))


@network
def test_finds_people_places_and_organisations(model):
    text = "In 1843 Ada Lovelace corresponded with Charles Babbage in London about the Royal Society."
    found = {(e["entity_group"], e["word"]) for e in model.predict(text)}
    assert {("PER", "Ada Lovelace"), ("PER", "Charles Babbage"), ("LOC", "London")} <= found


@network
def test_long_text_offsets_point_at_the_entities(model):
    text = ("Filler sentence about the weather and the harvest. " * 120) + "Ada Lovelace lived in London."
    ents = model.predict(text)
    assert any(e["entity_group"] == "PER" and text[e["start"]:e["end"]] == "Ada Lovelace" for e in ents)


@network
def test_agreement_with_the_reference_pipelines(model):
    """Reference entities were produced once by tests/dev/make_ner_reference.py
    with the transformers pipeline (the v2.0.7 model and the PyTorch version of
    the new one).  The ONNX int8 model must agree closely with its own PyTorch
    original and reasonably with the old English model."""
    with open(FIXTURE, encoding="utf-8") as f:
        text = f.read()
    with open(os.path.join(os.path.dirname(FIXTURE), "ner_reference.json"), encoding="utf-8") as f:
        ref = json.load(f)
    ours = {(e["entity_group"], e["word"]) for e in model.predict(text) if e["entity_group"] in {"PER", "ORG", "LOC"}}

    def f1(reference):
        reference = {(g, w) for g, w in reference if g in {"PER", "ORG", "LOC"}}
        tp = len(ours & reference)
        return 2 * tp / (len(ours) + len(reference))

    assert f1(ref["same_model_pytorch"]) >= 0.9
    assert f1(ref["v2_0_7_dbmdz"]) >= 0.7


@network
def test_ner_folder_outputs_keep_their_format(model, tmp_path, monkeypatch):
    import shutil
    from NLP import named_entity_recognition as ner
    monkeypatch.setattr(ner, "load_model", lambda: model)
    shutil.copyfile(FIXTURE, tmp_path / "letters.txt")
    (tmp_path / "markup.txt").write_text("Ada Lovelace wrote <b>to</b> Charles Babbage.", encoding="utf-8")
    ner.main(str(tmp_path))
    summary = (tmp_path / "Named_Entity_Recognition_Summary.html").read_text(encoding="utf-8")
    assert "<th>Entity Type</th>" in summary and "Ada Lovelace" in summary
    highlight = (tmp_path / "letters_Named_Entity_Recognition_Highlight.html").read_text(encoding="utf-8")
    assert "title='PER'>Ada Lovelace</span>" in highlight
    markup = (tmp_path / "markup_Named_Entity_Recognition_Highlight.html").read_text(encoding="utf-8")
    assert "&lt;b&gt;to&lt;/b&gt;" in markup  # document text is escaped, not interpreted
