"""Tests for cross-platform compatibility."""
import platform
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
