"""Which front end MDMT uses: a native window or the user's browser.

Windows and macOS use a native pywebview window (backed by the OS's own web
view).  Linux runs in the user's browser: pywebview there would need Qt or
GTK, which MDMT does not ship.  MDMT_BROWSER=1 forces browser mode elsewhere
(useful for development and testing).
"""
import os
import sys


def use_native_window() -> bool:
    if os.environ.get("MDMT_BROWSER") == "1":
        return False
    return sys.platform in ("win32", "darwin")
