"""Detecting an app folder whose symlinks were flattened by the extraction tool."""
import os
import sys

import pytest

from common.bundle import flattened_symlinks


@pytest.fixture
def bundle(tmp_path):
    lib = tmp_path / "llama_cpp" / "lib"
    lib.mkdir(parents=True)
    (lib / "libggml-cpu.so.0").write_bytes(b"\x7fELF" + b"\0" * 2000)
    (tmp_path / "libtiny.so").write_bytes(b"\x7fELF\x02\x01")       # a genuinely small binary
    (tmp_path / "notes.txt").write_text("llama_cpp/lib/libggml-cpu.so.0")  # not a library name
    return tmp_path


def test_a_text_file_holding_a_link_target_is_reported(bundle):
    (bundle / "libggml-cpu.so.0").write_text("llama_cpp/lib/libggml-cpu.so.0")
    assert flattened_symlinks(str(bundle)) == ["libggml-cpu.so.0"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_real_symlinks_are_fine(bundle):
    os.symlink("llama_cpp/lib/libggml-cpu.so.0", bundle / "libggml-cpu.so.0")
    assert flattened_symlinks(str(bundle)) == []


def test_text_pointing_nowhere_is_not_reported(bundle):
    (bundle / "libgone.so.1").write_text("lib/missing.so.1")
    assert flattened_symlinks(str(bundle)) == []


def test_macos_dylibs_are_checked_too(bundle):
    (bundle / "libggml.dylib").write_text("llama_cpp/lib/libggml-cpu.so.0")
    assert flattened_symlinks(str(bundle)) == ["libggml.dylib"]
