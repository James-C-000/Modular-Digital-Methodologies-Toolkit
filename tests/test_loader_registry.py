"""Tests for RAG loader registry dispatch."""
import os
import tempfile
import shutil
import pytest


@pytest.fixture
def sample_docs_dir():
    """Create a temp directory with one file of each supported type."""
    d = tempfile.mkdtemp()
    files = {
        "note.txt": "Plain text content.",
        "readme.md": "# Heading\nMarkdown content.",
        "data.csv": "name,value\nAlice,42\n",
        "config.json": '{"key": "value"}',
        "page.html": "<html><body><p>Hello HTML</p></body></html>",
    }
    for name, content in files.items():
        with open(os.path.join(d, name), "w") as f:
            f.write(content)
    yield d
    shutil.rmtree(d)


def test_get_loader_for_known_extensions():
    """Each supported extension maps to a loader class."""
    from RAG.qwen_rag import SUPPORTED_EXTENSIONS
    for ext in [".txt", ".pdf", ".md", ".html", ".csv", ".json", ".docx"]:
        assert ext in SUPPORTED_EXTENSIONS, f"Missing loader for {ext}"


def test_get_loader_returns_none_for_unknown():
    """Unknown extensions are not in the registry."""
    from RAG.qwen_rag import SUPPORTED_EXTENSIONS
    assert ".xyz" not in SUPPORTED_EXTENSIONS


def test_load_documents_finds_all_types(sample_docs_dir):
    """_load_documents discovers files of every supported text-based type."""
    from RAG.qwen_rag import QwenRAGSystem

    # Call _load_documents directly without full init.
    # We create a minimal instance by bypassing __init__.
    system = object.__new__(QwenRAGSystem)
    system.documents_dir = sample_docs_dir
    system.verbose = False
    system.n_threads = 2

    documents, file_count = system._load_documents()

    # 5 text-based files (no PDF or DOCX in this test — they need binary content)
    assert file_count == 5
    assert len(documents) >= 5  # CSVLoader produces one doc per row

    # Check sources include each file
    sources = {os.path.basename(d.metadata["source"]) for d in documents}
    assert sources == {"note.txt", "readme.md", "data.csv", "config.json", "page.html"}
