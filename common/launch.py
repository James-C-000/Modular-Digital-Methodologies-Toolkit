"""Snapshot of how the process was launched, taken before anything else runs.

Imported at the very top of app.py.  Windowed builds started without a
console (double-click in Explorer/Finder) may have no stdout/stderr at all;
common.logs then substitutes log-file writers.  The self-test reports this
snapshot so CI can tell which launch path it exercised.
"""
import os
import sys


def _describe(stream) -> str:
    if stream is None:
        return "missing"
    try:
        fd = stream.fileno()
    except (OSError, ValueError, AttributeError):
        return f"{type(stream).__name__} (no fd)"
    kind = "unknown"
    if sys.platform == "win32":
        try:
            import ctypes
            import msvcrt
            handle = msvcrt.get_osfhandle(fd)
            kind = {0: "unknown", 1: "disk", 2: "char", 3: "pipe"}.get(
                ctypes.windll.kernel32.GetFileType(handle), "other")
        except Exception as e:
            kind = f"error: {e}"
    else:
        try:
            import stat
            mode = os.fstat(fd).st_mode
            kind = ("tty" if os.isatty(fd) else "pipe" if stat.S_ISFIFO(mode)
                    else "file" if stat.S_ISREG(mode) else "char" if stat.S_ISCHR(mode) else "other")
        except OSError as e:
            kind = f"error: {e}"
    return f"fd {fd} ({kind})"


STDIO = {name: _describe(getattr(sys, name)) for name in ("stdin", "stdout", "stderr")}
