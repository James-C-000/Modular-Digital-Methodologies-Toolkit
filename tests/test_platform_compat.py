"""Tests for cross-platform compatibility."""
import os
import platform
import sys
from unittest.mock import patch


def test_multiprocessing_start_method_spawn_on_windows():
    """On Windows, the app should use 'spawn' (the only supported method)."""
    with patch("platform.system", return_value="Windows"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "spawn"


def test_multiprocessing_start_method_fork_on_linux():
    """On Linux, the app should use 'fork' for NiceGUI compatibility."""
    with patch("platform.system", return_value="Linux"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "fork"


def test_multiprocessing_start_method_fork_on_macos():
    """On macOS, the app should use 'fork' for NiceGUI compatibility."""
    with patch("platform.system", return_value="Darwin"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "fork"


def test_get_tesseract_path_returns_string():
    """get_tesseract_path should return a string path."""
    from config import get_tesseract_path
    result = get_tesseract_path()
    assert isinstance(result, str)


def test_get_tesseract_path_frozen_prefers_bundled(tmp_path):
    """When running as a frozen app, bundled Tesseract should be preferred."""
    from config import get_tesseract_path
    bundled_dir = tmp_path / "tesseract_bin"
    bundled_dir.mkdir()
    if platform.system() == "Windows":
        tesseract_bin = bundled_dir / "tesseract.exe"
    else:
        tesseract_bin = bundled_dir / "tesseract"
    tesseract_bin.touch()

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
        result = get_tesseract_path()
        assert isinstance(result, str)


def test_setup_frozen_tesseract_env_sets_path(tmp_path):
    """setup_frozen_env should prepend Tesseract dir to PATH."""
    from app import _setup_frozen_env
    bundled_dir = tmp_path / "tesseract_bin"
    bundled_dir.mkdir()
    if platform.system() == "Windows":
        (bundled_dir / "tesseract.exe").touch()
    else:
        (bundled_dir / "tesseract").touch()
    tessdata_dir = tmp_path / "tessdata"
    tessdata_dir.mkdir()

    old_path = os.environ.get("PATH", "")
    try:
        _setup_frozen_env(str(tmp_path))
        assert str(bundled_dir) in os.environ["PATH"]
    finally:
        os.environ["PATH"] = old_path
        os.environ.pop("TESSDATA_PREFIX", None)
