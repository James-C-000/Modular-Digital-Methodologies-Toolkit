"""Every batch function reports per-file progress and stops between files when cancelled."""
import os
import shutil
import threading

import pytest

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class Recorder:
    """on_progress that cancels after *stop_after* files have started."""

    def __init__(self, stop_after=None):
        self.calls, self.cancel, self.stop_after = [], threading.Event(), stop_after

    def __call__(self, done, total, name):
        self.calls.append((done, total, name))
        if self.stop_after is not None and len([c for c in self.calls if c[2]]) >= self.stop_after:
            self.cancel.set()


def _files(folder, names, text="Ada Lovelace met Charles Babbage in London."):
    for name in names:
        (folder / name).write_text(text, encoding="utf-8")


def test_ocr_batch(tmp_path, monkeypatch):
    from OCR import ocr_logic
    monkeypatch.setattr(ocr_logic, "run_ocr_file", lambda pdf, out, *a, **k: {"status": "success", "input": pdf})
    src = tmp_path / "in"
    src.mkdir()
    for n in ("a.pdf", "b.pdf", "c.pdf"):
        (src / n).write_bytes(b"%PDF-1.4")
    rec = Recorder()
    results = ocr_logic.run_ocr_batch(str(src), str(tmp_path / "out"), ["English"], on_progress=rec)
    assert len(results) == 3 and rec.calls[0] == (0, 3, "a.pdf") and rec.calls[-1] == (3, 3, "")
    rec = Recorder(stop_after=1)
    results = ocr_logic.run_ocr_batch(str(src), str(tmp_path / "out"), ["English"], on_progress=rec, cancel=rec.cancel)
    assert len(results) == 1


def test_transcribe_directory(tmp_path, monkeypatch):
    from Audio_Transcription import transcription_logic as tl
    monkeypatch.setattr(tl, "load_model", lambda name, root: object())
    monkeypatch.setattr(tl, "transcribe_file", lambda model, path, **k: {"status": "success", "input": path})
    for n in ("a.mp3", "b.mp3"):
        (tmp_path / n).write_bytes(b"")
    rec = Recorder(stop_after=1)
    results = tl.transcribe_directory(str(tmp_path), download_root=str(tmp_path), on_progress=rec, cancel=rec.cancel)
    assert len(results) == 1 and rec.calls[-1] == (1, 2, "")


def test_translate_directory(tmp_path, monkeypatch):
    from Translation import offline_translation as ot
    monkeypatch.setattr(ot, "installed_pairs", lambda root=None: {("fr", "en")})
    monkeypatch.setattr(ot, "route", lambda s, t, root=None, available=None: [("fr", "en")])
    monkeypatch.setattr(ot, "translate_text", lambda text, s, t, root=None: text.upper())
    _files(tmp_path, ["a.txt", "b.txt", "c.txt"])
    rec = Recorder(stop_after=2)
    results = ot.translate_directory(str(tmp_path), "fr", "en", on_progress=rec, cancel=rec.cancel)
    assert [r["status"] for r in results] == ["success", "success"]
    assert rec.calls[:2] == [(0, 3, "a.txt"), (1, 3, "b.txt")]


def test_keyword_search(tmp_path):
    from Advanced_Keyword_Search.advancedKeywordSearchLogic import search_directory
    src, out = tmp_path / "pdfs", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    for n in ("a.pdf", "b.pdf", "c.pdf"):
        shutil.copy(os.path.join(FIXTURES, "text_sample.pdf"), src / n)
    rec = Recorder()
    summary = search_directory(str(src), str(out), "the", on_progress=rec)
    assert summary["files"] == 3 and all(os.path.isfile(c) for c in summary["charts"])
    assert rec.calls[0] == (0, 3, "a.pdf") and rec.calls[-1] == (3, 3, "")
    rec = Recorder(stop_after=1)
    summary = search_directory(str(src), str(out), "the", on_progress=rec, cancel=rec.cancel)
    assert summary["files"] == 1 and summary["total"] == 3


def test_ner(tmp_path, monkeypatch):
    from NLP import named_entity_recognition as ner
    monkeypatch.setattr(ner, "run_ner_on_text", lambda text: [])
    _files(tmp_path, ["a.txt", "b.txt"])
    rec = Recorder(stop_after=1)
    summary = ner.main(str(tmp_path), on_progress=rec, cancel=rec.cancel)
    assert summary["files"] == 1 and summary["total"] == 2 and os.path.isfile(summary["summary"])
    with pytest.raises(NotADirectoryError):
        ner.main(str(tmp_path / "missing"))


def test_co_words(tmp_path):
    from NLP.co_word_analysis import main
    _files(tmp_path, ["a.txt", "b.txt"], text="mill river grain mill river grain " * 10)
    rec = Recorder()
    summary = main(str(tmp_path), stopword_language=None, on_progress=rec)
    assert summary["files"] == 2 and len(summary["images"]) == 2 and rec.calls[-1] == (2, 2, "")
    rec = Recorder(stop_after=1)
    assert main(str(tmp_path), stopword_language=None, on_progress=rec, cancel=rec.cancel)["files"] == 1


def test_relationships(tmp_path, monkeypatch):
    from NLP import relationship_extraction as rel
    monkeypatch.setattr(rel, "extract_entities_and_relationships", lambda text, types: [])
    _files(tmp_path, ["a.txt", "b.txt", "c.txt"])
    rec = Recorder(stop_after=2)
    result = rel.process_files_for_relationships(str(tmp_path), str(tmp_path), 0, 0, ["PER"],
                                                 on_progress=rec, cancel=rec.cancel)
    assert result["file_count"] == 2


def test_relationships_skip_text_extracted_by_an_earlier_run(tmp_path, monkeypatch):
    from NLP import relationship_extraction as rel
    seen = []
    monkeypatch.setattr(rel, "extract_text_from_file", lambda p: seen.append(os.path.basename(p)) or "text")
    monkeypatch.setattr(rel, "extract_entities_and_relationships", lambda text, types: [])
    shutil.copy(os.path.join(FIXTURES, "text_sample.pdf"), tmp_path / "letter.pdf")
    (tmp_path / "letter_text.txt").write_text("written by the previous run", encoding="utf-8")
    (tmp_path / "notes_text.txt").write_text("a user's own file, no matching PDF", encoding="utf-8")
    rel.process_files_for_relationships(str(tmp_path), str(tmp_path), 0, 0, ["PER"])
    assert sorted(seen) == ["letter.pdf", "notes_text.txt"]


def test_ner_writes_one_highlight_per_document_next_to_it(tmp_path, monkeypatch):
    from NLP import named_entity_recognition as ner
    monkeypatch.setattr(ner, "run_ner_on_text", lambda text: [])
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _files(tmp_path, ["a/report.txt", "b/report.txt", "b/report.pdf"])  # report.pdf is not a real PDF
    (tmp_path / "b" / "report.txt").write_bytes("Köln".encode("cp1252"))
    summary = ner.main(str(tmp_path))
    assert summary["files"] == 2 and summary["total"] == 3
    assert [s["input"] for s in summary["skipped"]] == [os.path.join("b", "report.pdf")]
    assert "could not be read" in summary["skipped"][0]["message"]
    assert "Köln" in (tmp_path / "b" / "report_2_Named_Entity_Recognition_Highlight.html").read_text(encoding="utf-8")
    assert (tmp_path / "a" / "report_Named_Entity_Recognition_Highlight.html").is_file()
    assert not list(tmp_path.glob("*_Highlight.html"))
