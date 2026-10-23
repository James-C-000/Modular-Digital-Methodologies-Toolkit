"""Filesystem path helpers."""
import os
import re

_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(name: str, max_length: int = 120) -> str:
    """Turn arbitrary text (e.g. a search keyword) into a filename valid on Windows.

    Removes ``<>:"/\\|?*`` and control characters, trailing dots and spaces,
    and prefixes reserved device names (``CON``, ``nul.txt``, ``COM1`` ...)
    with an underscore.  The result is never empty.
    """
    cleaned = _WINDOWS_FORBIDDEN.sub("", name).strip()
    cleaned = cleaned[:max_length].rstrip(". ")
    if not cleaned:
        return "_"
    if cleaned.split(".")[0].upper() in _WINDOWS_RESERVED:
        cleaned = "_" + cleaned
    return cleaned


def unique_safe_filenames(names, suffix: str = "") -> dict:
    """Map each name to a distinct safe filename (``name`` -> ``file+suffix``).

    Different names that sanitize to the same file (``a/b`` and ``ab``) get
    ``_2``, ``_3`` ... appended, compared case-insensitively as on Windows/macOS.
    """
    used = set()
    result = {}
    for name in names:
        base = safe_filename(name)
        candidate = base + suffix
        n = 2
        while candidate.casefold() in used:
            candidate = f"{base}_{n}{suffix}"
            n += 1
        used.add(candidate.casefold())
        result[name] = candidate
    return result


def same_path(a: str, b: str) -> bool:
    """True if two paths refer to the same location (symlinks, case, separators)."""
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
