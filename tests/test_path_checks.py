"""Input/output folder checks used by the pages, and finding the input files."""
import os
import sys

import pytest

from common.paths import find_files, folder_problem, is_inside, output_folder_problem, same_path


def _touch(folder, *names):
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")


def test_find_files_searches_sub_folders_and_matches_any_case(tmp_path):
    _touch(tmp_path, "b.pdf", "A.PDF", "notes.txt", "sub/deeper/c.pdf", "sub/readme.md")
    rel = [os.path.relpath(p, tmp_path) for p in find_files(str(tmp_path), [".pdf"])]
    assert rel == ["A.PDF", "b.pdf", os.path.join("sub", "deeper", "c.pdf")]
    assert len(find_files(str(tmp_path), (".pdf", ".txt"))) == 4
    assert find_files(str(tmp_path / "missing"), [".pdf"]) == []


def test_find_files_ignores_files_named_just_like_an_extension(tmp_path):
    _touch(tmp_path, ".pdf", ".md", "sub/.PDF", "a.pdf", ".hidden.pdf")
    rel = [os.path.relpath(p, tmp_path) for p in find_files(str(tmp_path), [".pdf", ".md"])]
    assert rel == [".hidden.pdf", "a.pdf"]


def test_find_files_exclude_and_hidden_folders(tmp_path):
    _touch(tmp_path, "a.txt", "a_fr.txt", ".index/cache.txt", "sub/.git/x.txt", "sub/b.txt")
    found = find_files(str(tmp_path), [".txt"], exclude=lambda p: p.endswith("_fr.txt"))
    assert len(found) == 4
    visible = find_files(str(tmp_path), [".txt"], skip_hidden_dirs=True)
    assert [os.path.relpath(p, tmp_path) for p in visible] == ["a.txt", "a_fr.txt", os.path.join("sub", "b.txt")]


def test_same_path_sees_through_dots_and_links(tmp_path):
    d = tmp_path / "scans"
    d.mkdir()
    assert same_path(str(d), str(tmp_path / "x" / ".." / "scans"))
    if sys.platform != "win32":
        (tmp_path / "link").symlink_to(d)
        assert same_path(str(d), str(tmp_path / "link"))


def test_is_inside(tmp_path):
    assert is_inside(str(tmp_path / "in" / "out"), str(tmp_path / "in"))
    assert not is_inside(str(tmp_path / "in"), str(tmp_path / "in"))
    assert not is_inside(str(tmp_path / "input2"), str(tmp_path / "in"))   # prefix, not parent


def test_folder_problem(tmp_path):
    assert folder_problem("") == "Choose a folder."
    assert folder_problem(str(tmp_path / "missing")) == "Folder not found."
    (tmp_path / "f.txt").write_text("x")
    assert folder_problem(str(tmp_path / "f.txt")) == "Folder not found."
    assert folder_problem(str(tmp_path)) is None


@pytest.mark.parametrize("out, reprocesses, problem", [
    ("in", False, "The output folder must differ from the input folder."),
    ("in/./", False, "The output folder must differ from the input folder."),
    ("in/ocr", True, "The output folder is inside the input folder, so running again would process the outputs too."),
    ("in/ocr", False, None),
    ("out", True, None),
    ("", True, "Choose an output folder."),
])
def test_output_folder_problem(tmp_path, out, reprocesses, problem):
    (tmp_path / "in").mkdir()
    out_path = str(tmp_path / out) if out else ""
    assert output_folder_problem(str(tmp_path / "in"), out_path, reprocesses_outputs=reprocesses) == problem


def test_output_folder_may_be_created_later(tmp_path):
    (tmp_path / "in").mkdir()
    assert output_folder_problem(str(tmp_path / "in"), str(tmp_path / "new" / "deep"), True) is None
    assert os.path.exists(tmp_path / "in")


@pytest.mark.skipif(sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="needs POSIX permissions (and not root)")
def test_folders_that_cannot_be_opened_are_reported(tmp_path):
    from common.paths import unreadable_entries
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "a.pdf").write_bytes(b"")
    (tmp_path / "b.pdf").write_bytes(b"")
    locked.chmod(0)
    try:
        unreadable = []
        found = find_files(str(tmp_path), [".pdf"], unreadable=unreadable)
        assert [os.path.basename(p) for p in found] == ["b.pdf"]
        entries = unreadable_entries(unreadable, str(tmp_path))
        assert [e["input"] for e in entries] == ["locked"] and "could not be opened" in entries[0]["message"]
    finally:
        locked.chmod(0o755)
