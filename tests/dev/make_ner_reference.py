"""Regenerate tests/fixtures/ner_reference.json (dev-only; needs torch + transformers).

Runs the transformers NER pipeline (aggregation_strategy="simple") on
tests/fixtures/ner_sample.txt with:
- v2_0_7_dbmdz: the English model MDMT v2.0.7 used, and
- same_model_pytorch: the PyTorch original of the model MDMT now runs as
  int8 ONNX, so the test can separate model differences from bugs in
  MDMT's own windowing/aggregation.

    pip install torch transformers   # in a scratch environment
    python tests/dev/make_ner_reference.py
"""
import json
import os

from transformers import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "..", "fixtures")
MODELS = {
    "v2_0_7_dbmdz": ("dbmdz/bert-large-cased-finetuned-conll03-english", "4c53496"),
    "same_model_pytorch": ("Davlan/bert-base-multilingual-cased-ner-hrl", "e756de7f7b8f64fea0c3d7c3872f1322fab747b1"),
}


def main():
    with open(os.path.join(FIXTURES, "ner_sample.txt"), encoding="utf-8") as f:
        text = f.read()
    out = {"text_file": "ner_sample.txt"}
    for key, (model, revision) in MODELS.items():
        ner = pipeline("ner", model=model, revision=revision, aggregation_strategy="simple")
        out[key] = sorted({(e["entity_group"], text[e["start"]:e["end"]]) for e in ner(text)})
        out[key + "_model"] = f"{model}@{revision}"
    with open(os.path.join(FIXTURES, "ner_reference.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    for key in MODELS:
        print(key, len(out[key]), out[key])


if __name__ == "__main__":
    main()
