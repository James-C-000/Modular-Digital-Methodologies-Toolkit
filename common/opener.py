"""Open URLs, files and folders with the user's default application."""
import os
import subprocess
import sys


def clean_child_env() -> dict:
    """Environment for launching *system* programs from a frozen app.

    PyInstaller (and MDMT's own Tesseract setup) put the bundle's library
    directory on ``LD_LIBRARY_PATH``; bundled libraries such as readline or
    ncurses then poison system tools like xdg-open.  Strip those entries.
    """
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        for var in ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH"):
            val = env.get(var, "")
            if val and base:
                cleaned = os.pathsep.join(
                    p for p in val.split(os.pathsep) if not p.startswith(base)
                )
                if cleaned:
                    env[var] = cleaned
                else:
                    env.pop(var, None)
        # PyInstaller saves the pre-launch value as LD_LIBRARY_PATH_ORIG.
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig:
            env["LD_LIBRARY_PATH"] = orig
    return env


def open_external(target: str):
    """Open a URL, file or folder in the default browser / file manager."""
    env = clean_child_env()
    if sys.platform == "linux":
        subprocess.Popen(["xdg-open", target], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target], env=env)
    elif sys.platform == "win32":
        os.startfile(target)
    else:
        import webbrowser
        webbrowser.open(target)
