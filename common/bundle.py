"""Checks on the integrity of a built (frozen) MDMT.

The Linux and macOS builds contain symbolic links between shared libraries.
Some archive tools do not support symlinks and extract each one as a small
text file holding the link's target; the dynamic loader then finds that text
file and fails ("file too short"), for example when RAGBot loads llama.cpp.
"""
import os

EXTRACTION_HELP = (
    "MDMT was extracted with a tool that does not keep symbolic links, so some features (such as RAGBot) "
    "will not work. Delete the MDMT folder and extract the download again: on Linux with your archive manager "
    "or `tar -xzf mdmt-linux-x86_64.tar.gz`, on macOS by double-clicking the zip in Finder."
)

# Set at startup (app.main) when a frozen build finds flattened symlinks.
PROBLEM: str | None = None


def _is_library(name: str) -> bool:
    return ".so" in name or name.endswith(".dylib")


def flattened_symlinks(base: str, max_bytes: int = 512) -> list[str]:
    """Library files under *base* that are text files naming another file there.

    Returns their paths relative to *base*.  Real symlinks and genuinely small
    libraries are not reported.
    """
    found = []
    for root, _dirs, names in os.walk(base):
        for name in names:
            path = os.path.join(root, name)
            if not _is_library(name) or os.path.islink(path):
                continue
            try:
                if os.path.getsize(path) > max_bytes:
                    continue
                with open(path, "rb") as f:
                    target = f.read().decode("utf-8").strip()
            except (OSError, UnicodeDecodeError):
                continue
            if target and "\n" not in target and os.path.isfile(os.path.join(root, target)):
                found.append(os.path.relpath(path, base))
    return sorted(found)
