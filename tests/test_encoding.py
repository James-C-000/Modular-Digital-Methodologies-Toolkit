"""Windows text-encoding and filename regressions.

On Windows with Python 3.12, ``open()`` without ``encoding=`` uses cp1252, so
non-Latin keywords and transcripts raised UnicodeEncodeError, and CSVs written
without ``newline=""`` had a blank line after every row.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from common.paths import output_stems, safe_filename, unique_safe_filenames
from common.text_files import document_text, read_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "tests", "fixtures", "text_sample.pdf")

# Prepended to child scripts: make open() behave like Python 3.12 on Windows,
# i.e. cp1252 when no encoding is given and "\n" -> "\r\n" translation when no
# newline is given.  Filenames are unaffected (Windows stores them as UTF-16).
_WINDOWS_OPEN_SHIM = r'''
import builtins, io
_real_open = io.open
def _windows_open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, *a, **k):
    if "b" not in mode:
        if encoding is None:
            encoding = "cp1252"
        if newline is None and any(c in mode for c in "wax+"):
            newline = "\r\n"
    return _real_open(file, mode, buffering, encoding, errors, newline, *a, **k)
builtins.open = io.open = _windows_open
'''


def _run_as_if_on_windows(code: str):
    """Run *code* in a child process with Windows' legacy open() defaults."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(f"import sys; sys.path.insert(0, {ROOT!r})\n" + _WINDOWS_OPEN_SHIM + code)
    try:
        proc = subprocess.run([sys.executable, f.name], cwd=ROOT,
                              env=dict(os.environ, MPLBACKEND="Agg"),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        os.unlink(f.name)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return proc


@pytest.mark.parametrize("raw,expected", [
    ("Москва", "Москва"),
    ("日本語", "日本語"),
    ('a<b>c:"d/e\\f|g?h*', "abcdefgh"),
    ("trailing. . ", "trailing"),
    ("CON", "_CON"),
    ("nul.txt", "_nul.txt"),
    ("com1", "_com1"),
    ("console", "console"),
    ("???", "_"),
    ("", "_"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_unique_safe_filenames_disambiguates_collisions():
    mapping = unique_safe_filenames(["a/b", "ab", "AB", "c"], ".csv")
    assert mapping == {"a/b": "ab.csv", "ab": "ab_2.csv", "AB": "AB_3.csv", "c": "c.csv"}
    assert unique_safe_filenames(["data_overview", "c"], ".csv", reserved=["Data_Overview.csv"]) == {
        "data_overview": "data_overview_2.csv", "c": "c.csv"}


def test_windows_shim_reproduces_the_bugs(tmp_path):
    """Sanity-check the harness: unspecified encoding/newline must misbehave."""
    target = tmp_path / "x.txt"
    _run_as_if_on_windows(
        "import csv\n"
        "try:\n"
        f"    open({str(target)!r}, 'w').write('\u043c')\n"
        "    raise SystemExit('cp1252 accepted Cyrillic?')\n"
        "except UnicodeEncodeError:\n"
        "    pass\n"
        f"with open({str(target)!r}, 'w') as f:\n"
        "    csv.writer(f).writerow(['a'])\n"
    )
    assert target.read_bytes() == b"a\r\r\n"


def test_keyword_search_handles_non_latin_keywords_and_writes_excel_csv(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    out = tmp_path / "out"
    pdf_dir.mkdir()
    out.mkdir()
    shutil.copyfile(PDF, pdf_dir / "sample.pdf")
    _run_as_if_on_windows(
        "from Advanced_Keyword_Search.advancedKeywordSearchLogic import search_directory\n"
        f"search_directory({str(pdf_dir)!r}, {str(out)!r}, 'москва\\nkyiv\\ncon', context_words=6)\n"
    )

    for name in ("москва.csv", "kyiv.csv", "_con.csv", "Data_Overview.csv"):
        raw = (out / name).read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), f"{name}: Excel needs a UTF-8 BOM"
        assert raw.count(b"\xef\xbb\xbf") == 1, f"{name}: BOM repeated on append"
        assert b"\r\r\n" not in raw, f"{name}: blank rows on Windows"

    with open(out / "москва.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Year", "Page", "Context: москва"]
    assert len(rows) == 3 and all("москва" in r[2] for r in rows[1:])

    with open(out / "Data_Overview.csv", encoding="utf-8-sig", newline="") as f:
        overview = list(csv.reader(f))
    assert overview[0] == ["Year", "москва", "kyiv", "con"]
    assert overview[1] == ["sample.pdf", "2", "2", "1"]
    assert (out / "totalBar.png").stat().st_size > 0


def test_transcript_is_written_as_utf8(tmp_path):
    out = tmp_path / "t.txt"
    _run_as_if_on_windows(
        "from Audio_Transcription.transcription_logic import transcribe_file\n"
        "class Seg: text = ' Привет, 世界'\n"
        "class Info: language = 'ru'\n"
        "class Model:\n"
        "    def transcribe(self, *a, **k): return iter([Seg()]), Info()\n"
        f"r = transcribe_file(Model(), 'in.mp3', {str(out)!r})\n"
        "assert r['status'] == 'success', r\n"
    )
    assert out.read_bytes().decode("utf-8") == "Привет, 世界"


@pytest.mark.parametrize("raw, expected", [
    ("Köln".encode("utf-8"), "Köln"),
    (b"\xef\xbb\xbf" + "Köln".encode("utf-8"), "Köln"),        # BOM from Notepad
    ("Café – “quoted”".encode("cp1252"), "Café – “quoted”"),    # older Windows programs
    (b"caf\xe9 \x81", "café \x81"),                              # not valid cp1252 either: Latin-1
])
def test_read_text_decodes_legacy_encodings(tmp_path, raw, expected):
    (tmp_path / "t.txt").write_bytes(raw)
    assert read_text(str(tmp_path / "t.txt")) == expected


def test_document_text_reads_pdfs_and_text_files(tmp_path):
    (tmp_path / "t.TXT").write_bytes("Köln".encode("cp1252"))
    assert document_text(str(tmp_path / "t.TXT")) == "Köln"
    assert document_text(PDF).strip()


def test_output_stems_disambiguate_files_in_the_same_folder():
    stems = output_stems([os.path.join("a", "report.txt"), os.path.join("a", "Report.pdf"),
                          os.path.join("b", "report.txt"), os.path.join("a", "report_2.txt")])
    assert stems == {os.path.join("a", "Report.pdf"): "Report", os.path.join("a", "report.txt"): "report_2",
                     os.path.join("a", "report_2.txt"): "report_2_2", os.path.join("b", "report.txt"): "report"}
