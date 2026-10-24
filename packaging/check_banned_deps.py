"""Fail if a removed dependency creeps back into the requirements.

    python packaging/check_banned_deps.py

Checks requirements/lock-*.txt (everything installed) and requirements/base.in
(direct requirements). Extend BANNED as later phases remove more packages.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ = os.path.join(ROOT, "requirements")

# Not allowed anywhere in a lock file.
BANNED = {"nltk", "pandas", "googletrans", "pypdf", "openai-whisper", "openpyxl", "future"}
# Not allowed in the Linux lock (Linux runs in the browser, without Qt).
BANNED_LINUX = {"pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6", "qtpy", "pywebview"}
# Not allowed as direct requirements (may still arrive transitively).
BANNED_DIRECT = {"requests"}


def _names(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", line)
            if m and not line.lstrip().startswith(("#", "-")):
                yield re.sub(r"[-_.]+", "-", m.group(1)).lower()


def main() -> int:
    problems = []
    for name in sorted(os.listdir(REQ)):
        if name.startswith("lock-") and name.endswith(".txt"):
            found = set(_names(os.path.join(REQ, name)))
            banned = BANNED | (BANNED_LINUX if name == "lock-linux.txt" else set())
            problems += [f"{name}: {pkg}" for pkg in sorted(found & banned)]
    direct = set(_names(os.path.join(REQ, "base.in")))
    problems += [f"base.in (direct): {pkg}" for pkg in sorted(direct & BANNED_DIRECT)]
    for p in problems:
        print("BANNED DEPENDENCY:", p)
    print(f"{len(problems)} banned dependencies found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
