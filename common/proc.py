"""Subprocess helpers."""
import subprocess
import sys


def no_window_kwargs() -> dict:
    """Extra ``subprocess`` kwargs that stop console windows flashing on Windows.

    The frozen Windows build is a GUI (``console=False``) executable, so every
    console child process would otherwise open a visible terminal window.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def hide_console_windows_in(module, names=("subprocess_run", "Popen")):
    """Make a third-party module's subprocess calls window-less on Windows.

    ocrmypdf starts Tesseract (a console program) for every page without
    ``CREATE_NO_WINDOW``, so a GUI build would flash a terminal per page.  It
    binds ``subprocess.run``/``Popen`` at import time, so we wrap those names
    in its namespace.  No-op on other platforms.
    """
    flags = no_window_kwargs()
    if not flags:
        return
    for name in names:
        original = getattr(module, name, None)
        if original is None or getattr(original, "_mdmt_no_window", False):
            continue

        def wrapper(*args, _original=original, **kwargs):
            if not kwargs.get("creationflags"):
                kwargs.update(flags)
            return _original(*args, **kwargs)

        wrapper._mdmt_no_window = True
        setattr(module, name, wrapper)
