import json
import os
import shutil

import pytest

from RAG.loaders import SUPPORTED_EXTENSIONS, find_documents, load_document

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _texts(path):
    return [s.text for s in load_document(path)]


def test_pdf_sections_are_pages_numbered_from_one():
    sections = load_document(os.path.join(FIX, "text_sample.pdf"))
    assert [s.page for s in sections] == [1, 2]
    assert "Ada Lovelace" in sections[1].text


def test_docx_body_tables_and_accents():
    text = "\n".join(_texts(os.path.join(FIX, "rag_sample.docx")))
    assert "Harbour Ledger, 1788" in text
    assert "The brig Endeavour arrived from Lisbon" in text
    assert "Café owners" in text and "£14 6s" in text
    assert "Bordeaux" in text and "claret" in text  # table cells
    assert "tracking" not in text


def test_html_skips_script_and_style_and_keeps_blocks_apart():
    text = "\n".join(_texts(os.path.join(FIX, "rag_sample.html")))
    assert "this script text must not be indexed" not in text and "font-family" not in text
    assert "£14 6s" in text and "Café owners" in text
    assert "Pilotage paid in full." in text and "Quarantine waived." in text
    assert "full.Quarantine" not in text  # list items are separate lines


def test_plain_text_markdown_json_and_csv(tmp_path):
    (tmp_path / "a.txt").write_text("Plain text about the mill.", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Heading\nMarkdown body.", encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps({"ship": {"name": "Swift", "cargo": ["claret"]}}), encoding="utf-8")
    (tmp_path / "d.csv").write_text("ship,port\nSwift,Bordeaux\nEndeavour,Lisbon\n", encoding="utf-8")
    assert _texts(tmp_path / "a.txt") == ["Plain text about the mill."]
    assert "Markdown body." in _texts(tmp_path / "b.md")[0]
    js = _texts(tmp_path / "c.json")[0]
    assert "ship.name: Swift" in js and "ship.cargo[0]: claret" in js
    rows = _texts(tmp_path / "d.csv")[0].splitlines()
    assert rows == ["ship: Swift | port: Bordeaux", "ship: Endeavour | port: Lisbon"]


def test_legacy_encoding_text_file(tmp_path):
    (tmp_path / "old.txt").write_bytes("Ein Brief aus Köln".encode("cp1252"))
    assert _texts(tmp_path / "old.txt") == ["Ein Brief aus Köln"]


def test_find_documents_is_recursive_and_filters_extensions(tmp_path):
    shutil.copyfile(os.path.join(FIX, "rag_sample.html"), tmp_path / "x.HTML")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "note.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    assert [os.path.relpath(p, tmp_path) for p in find_documents(str(tmp_path))] == [
        os.path.join("sub", "note.txt"), "x.HTML"]
    assert {".txt", ".pdf", ".md", ".json", ".html", ".htm", ".csv", ".docx"} == set(SUPPORTED_EXTENSIONS)


def test_unreadable_document_raises_a_clear_error(tmp_path):
    bad = tmp_path / "broken.docx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="broken.docx"):
        load_document(str(bad))


def test_docx_table_rows_keep_their_cells_together():
    text = "\n".join(_texts(os.path.join(FIX, "rag_sample.docx")))
    assert "Swift | Bordeaux | claret" in text
