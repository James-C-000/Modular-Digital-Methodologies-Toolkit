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


def output_stems(paths) -> dict:
    """Map each input path to the name its output files start with.

    That is the file name without its extension, plus ``_2``, ``_3`` ... when
    another file in the same folder has the same one (``report.pdf`` and
    ``report.txt``), compared case-insensitively as on Windows/macOS.
    """
    used = set()
    result = {}
    for path in sorted(paths):
        folder, name = os.path.split(path)
        stem = os.path.splitext(name)[0]
        candidate, n = stem, 2
        while (folder, candidate.casefold()) in used:
            candidate = f"{stem}_{n}"
            n += 1
        used.add((folder, candidate.casefold()))
        result[path] = candidate
    return result


def same_path(a: str, b: str) -> bool:
    """True if two paths refer to the same location (symlinks, case, separators)."""
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def is_inside(child: str, parent: str) -> bool:
    """True if *child* is strictly below *parent* (after resolving links and case)."""
    c = os.path.normcase(os.path.realpath(child))
    p = os.path.normcase(os.path.realpath(parent))
    try:
        return c != p and os.path.commonpath([c, p]) == p
    except ValueError:  # different drives on Windows
        return False


def folder_problem(path: str) -> str | None:
    """Why *path* cannot be used as an input folder, or None."""
    if not path:
        return "Choose a folder."
    if not os.path.isdir(path):
        return "Folder not found."
    return None


def output_folder_problem(input_dir: str, output_dir: str, reprocesses_outputs: bool) -> str | None:
    """Why *output_dir* cannot be used with *input_dir*, or None.

    reprocesses_outputs: the tool searches the input folder recursively for
    files of the kind it writes (OCR reads and writes PDFs), so an output
    folder inside the input folder would be processed again on the next run.
    """
    if not output_dir:
        return "Choose an output folder."
    if same_path(input_dir, output_dir):
        return "The output folder must differ from the input folder."
    if reprocesses_outputs and is_inside(output_dir, input_dir):
        return "The output folder is inside the input folder, so running again would process the outputs too."
    return None
