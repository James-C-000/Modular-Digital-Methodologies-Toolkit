"""Managed Tesseract language data.

MDMT keeps every Tesseract language file in one directory under the app data
folder (``config.get_tessdata_dir()``) and points ``TESSDATA_PREFIX`` at it
for the whole process, so languages downloaded in-app are the ones Tesseract
actually sees.  ocrmypdf has no option for choosing a tessdata directory; it
runs the ``tesseract`` binary, which reads ``TESSDATA_PREFIX`` (with
Tesseract 5 the variable names the tessdata directory itself).

On first run the managed directory is seeded from the bundled tessdata (frozen
builds) or the system tessdata (source runs) with:

- ``eng`` and ``osd`` (``osd`` is required by "Rotate Pages"), and
- ``configs/``, ``tessconfigs/`` and ``pdf.ttf``.  ocrmypdf invokes
  ``tesseract ... hocr txt``, and those config names are files in
  ``configs/``; without them every OCR run fails with
  "read_params_file: Can't open hocr".
"""
import os
import re
import shutil
import subprocess
import sys

from common.proc import no_window_kwargs
from config import get_tessdata_dir

SEED_LANGUAGES = ("eng", "osd")
SUPPORT_ENTRIES = ("configs", "tessconfigs", "pdf.ttf")

# Common system locations, tried after asking the tesseract binary itself.
_SYSTEM_TESSDATA_CANDIDATES = (
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
    "/usr/local/share/tessdata",
    "/opt/homebrew/share/tessdata",
    os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Tesseract-OCR", "tessdata"),
)


def installed_languages(tessdata_dir: str | None = None) -> set[str]:
    """Return the language codes with a ``.traineddata`` file in *tessdata_dir*."""
    tessdata_dir = tessdata_dir or get_tessdata_dir()
    try:
        names = os.listdir(tessdata_dir)
    except OSError:
        return set()
    return {n[: -len(".traineddata")] for n in names if n.endswith(".traineddata")}


def _bundled_tessdata_dir() -> str | None:
    if not getattr(sys, "frozen", False):
        return None
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    path = os.path.join(base, "tessdata")
    return path if os.path.isdir(path) else None


def _tesseract_default_tessdata(tesseract_cmd: str = "tesseract") -> str | None:
    """Ask the tesseract binary for its compiled-in tessdata directory.

    ``tesseract --list-langs`` prints ``List of available languages in "<dir>"``.
    ``TESSDATA_PREFIX`` is removed from the child's environment so the answer
    is the default, not whatever we have already set.
    """
    env = {k: v for k, v in os.environ.items() if k != "TESSDATA_PREFIX"}
    try:
        out = subprocess.run(
            [tesseract_cmd, "--list-langs"], capture_output=True, text=True,
            timeout=15, env=env, **no_window_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r'languages in "([^"]+)"', out.stdout + out.stderr)
    if match:
        path = match.group(1).rstrip("/\\")
        if os.path.isdir(path):
            return path
    return None


def find_seed_source() -> str | None:
    """Locate a tessdata directory to seed from (bundled first, then system)."""
    bundled = _bundled_tessdata_dir()
    if bundled:
        return bundled
    from_binary = _tesseract_default_tessdata(shutil.which("tesseract") or "tesseract")
    if from_binary and os.path.isfile(os.path.join(from_binary, "eng.traineddata")):
        return from_binary
    for candidate in _SYSTEM_TESSDATA_CANDIDATES:
        if os.path.isfile(os.path.join(candidate, "eng.traineddata")):
            return candidate
    return None


def seed_tessdata(managed_dir: str, source_dir: str | None) -> list[str]:
    """Copy seed languages and support files missing from *managed_dir*.

    Existing files are never overwritten (a user may have downloaded a
    different variant).  Returns the names that were copied.
    """
    if not source_dir or not os.path.isdir(source_dir):
        return []
    if os.path.normcase(os.path.realpath(source_dir)) == os.path.normcase(os.path.realpath(managed_dir)):
        return []
    os.makedirs(managed_dir, exist_ok=True)
    copied = []
    for code in SEED_LANGUAGES:
        name = f"{code}.traineddata"
        src = os.path.join(source_dir, name)
        dst = os.path.join(managed_dir, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            _atomic_copy(src, dst)
            copied.append(name)
    for name in SUPPORT_ENTRIES:
        src = os.path.join(source_dir, name)
        dst = os.path.join(managed_dir, name)
        if os.path.isdir(src):
            for root, _dirs, files in os.walk(src):
                rel = os.path.relpath(root, src)
                target_root = os.path.normpath(os.path.join(dst, rel))
                os.makedirs(target_root, exist_ok=True)
                for f in files:
                    target = os.path.join(target_root, f)
                    if not os.path.exists(target):
                        _atomic_copy(os.path.join(root, f), target)
                        copied.append(os.path.relpath(target, managed_dir))
        elif os.path.isfile(src) and not os.path.exists(dst):
            _atomic_copy(src, dst)
            copied.append(name)
    return copied


def _atomic_copy(src: str, dst: str):
    tmp = dst + ".part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def configure_tessdata() -> str:
    """Seed the managed tessdata dir and point ``TESSDATA_PREFIX`` at it.

    Call once at startup, before any OCR runs.  Returns the managed directory.
    """
    managed = get_tessdata_dir()
    seed_tessdata(managed, find_seed_source())
    os.environ["TESSDATA_PREFIX"] = managed
    return managed
