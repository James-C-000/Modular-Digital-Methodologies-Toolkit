"""The licenses/ folder of a build: every bundled component's own license files."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "packaging"))
import collect_licenses as cl  # noqa: E402

PLATFORM = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


@pytest.fixture
def collected(tmp_path, monkeypatch):
    # llama-cpp-python is built separately and not installed for most test runs.
    monkeypatch.setattr(cl, "EXTRA_DISTRIBUTIONS", ())
    return cl.collect_licenses(str(tmp_path / "licenses"), PLATFORM, tesseract_dir=str(tmp_path))


def _normalized(name):   # PEP 503: "pdfminer.six" is "pdfminer-six"
    return re.sub(r"[-_.]+", "-", name).lower()


def test_every_locked_package_is_listed_and_cpython_included(collected):
    index = open(os.path.join(collected, "README.txt"), encoding="utf-8").read()
    listed = {_normalized(line.split(" ", 1)[0]) for line in index.splitlines() if " " in line}
    for name in cl.locked_distributions(PLATFORM):
        assert _normalized(name) in listed, name
    assert os.path.isfile(os.path.join(collected, "python", "CPython", "LICENSE.txt"))


def test_native_libraries_inside_wheels_keep_their_notices(collected):
    """Pillow and NumPy carry FreeType, libjpeg, OpenBLAS, libgfortran ...: their texts must come along."""
    pillow = open(os.path.join(collected, "python", "pillow", "LICENSE"), encoding="utf-8").read()
    assert "MIT-CMU" in pillow and "FreeType" in pillow
    numpy = open(os.path.join(collected, "python", "numpy", "LICENSE.txt"), encoding="utf-8").read()
    assert "OpenBLAS" in numpy
    assert os.path.isfile(os.path.join(collected, "python", "onnxruntime", "onnxruntime", "ThirdPartyNotices.txt"))


def test_windows_takes_the_license_files_of_the_tesseract_folder(tmp_path, monkeypatch):
    tess = tmp_path / "Tesseract-OCR"
    (tess / "doc").mkdir(parents=True)
    (tess / "doc" / "LICENSE").write_text("Apache License 2.0", encoding="utf-8")
    (tess / "libleptonica.dll").write_bytes(b"")
    lines = cl.system_licenses(str(tmp_path / "out"), "windows", tesseract_dir=str(tess))
    assert (tmp_path / "out" / "system" / "Tesseract-OCR" / "doc" / "LICENSE").is_file()
    assert "1 licence file(s)" in lines[0]
