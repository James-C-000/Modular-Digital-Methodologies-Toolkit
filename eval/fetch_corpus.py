"""Download the evaluation corpus (public-domain Project Gutenberg texts).

    python -m eval.fetch_corpus [--dest eval/corpus]

Each text is saved without the Gutenberg header and license footer, and every
gold quote in eval/questions.jsonl is checked against it: a newer Gutenberg
edition that moved or reworded a gold passage fails here, not silently later.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.metrics import normalize  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
USER_AGENT = "MDMT-eval/1.0 (+https://github.com/James-C-000/Modular-Digital-Methodologies-Toolkit)"


def strip_gutenberg(text: str) -> str:
    """The book between the '*** START OF' and '*** END OF' marker lines."""
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("*** START OF")), -1)
    end = next((i for i, line in enumerate(lines) if line.startswith("*** END OF")), len(lines))
    return "\n".join(lines[start + 1:end]).strip()


def load_corpus_spec() -> list[dict]:
    with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as f:
        return json.load(f)["documents"]


def load_questions(path: str | None = None) -> list[dict]:
    with open(path or os.path.join(EVAL_DIR, "questions.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def missing_gold(dest: str, questions: list[dict]) -> list[str]:
    """Gold quotes that no longer occur in the fetched texts."""
    bodies, missing = {}, []
    for q in questions:
        for g in q["gold"]:
            if g["file"] not in bodies:
                with open(os.path.join(dest, g["file"]), encoding="utf-8") as f:
                    bodies[g["file"]] = normalize(f.read())
            if normalize(g["quote"]) not in bodies[g["file"]]:
                missing.append(f"{q['id']}: {g['file']}: {g['quote']!r}")
    return missing


def corpus_hashes(dest: str) -> dict:
    """sha256 of each fetched text, recorded with every result."""
    hashes = {}
    for doc in load_corpus_spec():
        with open(os.path.join(dest, doc["file"]), "rb") as f:
            hashes[doc["file"]] = hashlib.sha256(f.read()).hexdigest()
    return hashes


def fetch(dest: str):
    os.makedirs(dest, exist_ok=True)
    for doc in load_corpus_spec():
        path = os.path.join(dest, doc["file"])
        if not os.path.exists(path):
            url = URL.format(id=doc["gutenberg_id"])
            print(f"Fetching {doc['title']} ({url})")
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = strip_gutenberg(resp.read().decode("utf-8-sig"))
            with open(path + ".part", "w", encoding="utf-8", newline="\n") as f:
                f.write(text + "\n")
            os.replace(path + ".part", path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", default=os.path.join(EVAL_DIR, "corpus"))
    args = parser.parse_args(argv)
    fetch(args.dest)
    missing = missing_gold(args.dest, load_questions())
    for m in missing:
        print("gold quote not found:", m, file=sys.stderr)
    print(f"Corpus ready in {args.dest}" if not missing else f"{len(missing)} gold quotes missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
