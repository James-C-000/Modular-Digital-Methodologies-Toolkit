import csv
import os
import re
import shutil

import pytest

from NLP import relationship_extraction as rel


class FakeNer:
    """Finds a fixed set of names; stands in for the ONNX model."""
    NAMES = {"Ada Lovelace": "PER", "Charles Babbage": "PER", "London": "LOC",
             "Royal Society": "ORG", "1843": "DATE"}

    def predict(self, text):
        ents = []
        for name, label in self.NAMES.items():
            for m in re.finditer(re.escape(name), text):
                ents.append({"entity_group": label, "word": name, "start": m.start(), "end": m.end(), "score": 0.99})
        return sorted(ents, key=lambda e: e["start"])


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    monkeypatch.setattr(rel, "load_model", lambda: FakeNer())


def test_pairs_within_a_sentence_with_connecting_words():
    text = "In 1843 Ada Lovelace corresponded with Charles Babbage about the engine. London was foggy that year."
    rows = rel.extract_entities_and_relationships(text, ["PER", "LOC"])
    assert rows == [["Ada Lovelace", "PER", "corresponded with", "Charles Babbage", "PER",
                     "In 1843 Ada Lovelace corresponded with Charles Babbage about the engine."]]


def test_other_entities_are_left_out_of_the_connecting_words():
    text = "Ada Lovelace met Charles Babbage in London last spring."
    rows = rel.extract_entities_and_relationships(text, ["PER", "LOC"])
    assert ["Ada Lovelace", "PER", "met in", "London", "LOC"] == rows[1][:5]


def test_adjacent_entities_get_the_default_relationship_and_long_gaps_are_shortened():
    text = ("Ada Lovelace, Charles Babbage and many other people whose names were never written down "
            "anywhere at all visited London.")
    rows = {(r[0], r[3]): r[2] for r in rel.extract_entities_and_relationships(text, ["PER", "LOC"])}
    assert rows[("Ada Lovelace", "Charles Babbage")] == "is connected to"
    assert rows[("Charles Babbage", "London")].endswith("…")
    assert len(rows[("Charles Babbage", "London")].split()) == 9  # 8 words + ellipsis


def test_entity_type_filter_and_short_sentences():
    text = "Ada Lovelace met Charles Babbage near London. Lovelace left."
    assert all(r[1] == r[4] == "PER" for r in rel.extract_entities_and_relationships(text, ["PER"]))
    assert rel.extract_entities_and_relationships("Ada Lovelace, London.", ["PER", "LOC"]) == []


def test_folder_run_writes_excel_csv_and_graph(tmp_path):
    (tmp_path / "letters.txt").write_text(
        "Ada Lovelace corresponded with Charles Babbage in London about the Royal Society in 1843.",
        encoding="utf-8")
    result = rel.process_files_for_relationships(
        str(tmp_path), str(tmp_path), None, extract_text=0, generate_graph=1,
        entity_types=["PER", "ORG", "LOC"])
    assert result["status"] == "success", result["message"]
    raw = (tmp_path / "relationships.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with open(tmp_path / "relationships.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Source", "Source_Type", "Relationship", "Target", "Target_Type", "Sentence", "File"]
    assert result["relationship_count"] == len(rows) - 1 == 6
    assert all(r[6] == "letters.txt" for r in rows[1:])
    assert (tmp_path / "relationship_network.png").stat().st_size > 0
    assert (tmp_path / "per_network.png").exists()


def test_no_entities_is_a_warning(tmp_path):
    (tmp_path / "plain.txt").write_text("Nothing notable happened on the farm this week at all.", encoding="utf-8")
    result = rel.process_files_for_relationships(str(tmp_path), str(tmp_path), None, 0, 1, ["PER"])
    assert result["status"] == "warning"


def test_subfolders_saved_text_and_file_column(tmp_path):
    sentence = "Ada Lovelace corresponded with Charles Babbage about engines and numbers."
    for box in ("box1", "box2"):
        (tmp_path / box).mkdir()
        (tmp_path / box / "letters.txt").write_text(sentence, encoding="utf-8")
    shutil.copy(os.path.join(os.path.dirname(__file__), "fixtures", "text_sample.pdf"), tmp_path / "box1" / "scan.pdf")
    (tmp_path / "box2" / "blank.txt").write_text("", encoding="utf-8")
    seen = []
    real = rel.extract_text_from_file

    def reading(path):
        seen.append(os.path.relpath(path, tmp_path))
        return real(path)

    rel.extract_text_from_file = reading
    try:
        result = rel.process_files_for_relationships(str(tmp_path), str(tmp_path), None, 1, 0, ["PER"])
        assert (tmp_path / "box1" / "scan_text.txt").is_file()          # next to the PDF
        assert not list(tmp_path.rglob("letters_text.txt"))           # only PDFs' text is saved
        assert result["skipped"] == [{"input": os.path.join("box2", "blank.txt"),
                                      "message": "no text (scanned PDF? run OCR first)"}]
        with open(tmp_path / "relationships.csv", encoding="utf-8-sig", newline="") as f:
            files = {r[6] for r in list(csv.reader(f))[1:]}
        assert files == {os.path.join("box1", "letters.txt"), os.path.join("box2", "letters.txt")}
        seen.clear()
        rel.process_files_for_relationships(str(tmp_path), str(tmp_path), None, 1, 0, ["PER"])
        assert os.path.join("box1", "scan_text.txt") not in seen      # saved text is not processed again
    finally:
        rel.extract_text_from_file = real
