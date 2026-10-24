"""Check eval/questions.jsonl against the corpus, so a reviewer need not read the books.

    python -m eval.check_questions            # report
    python -m eval.check_questions --write    # also rewrite quotes as full sentences

For each question it:
  * finds every gold quote in its book and widens it to the whole sentence(s);
  * checks that each accepted answer occurs in that passage (answers that do
    not are spellings or paraphrases and belong in "equivalents");
  * checks that the passage fits inside one indexed chunk, since relevance is
    judged per chunk;
  * lists every other place in the book where an answer occurs: each is either
    a missing gold passage or a sign that the question is ambiguous;
  * flags answer strings too short to match safely.
"""
import argparse
import json
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.fetch_corpus import EVAL_DIR, load_questions  # noqa: E402
from eval.metrics import contains_term, fold, normalize  # noqa: E402
from NLP.text_utils import sentence_spans  # noqa: E402

_QUOTE_CHARS = {"'": "['’‘]", '"': '["“”«»]', "-": "[-—–]"}
MIN_ANSWER_CHARS = 3
MAX_OTHER_HITS = 4


def _quote_pattern(quote: str) -> re.Pattern:
    words = []
    for word in quote.split():
        words.append("".join(_QUOTE_CHARS.get(ch, re.escape(ch)) for ch in word))
    return re.compile(r"\s+".join(words), re.IGNORECASE)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def locate(text: str, quote: str, sentences: list[tuple[int, int]]):
    """(start, end) of the sentence(s) containing *quote*, or None."""
    m = _quote_pattern(quote).search(text)
    if not m:
        return None
    covering = [(s, e) for s, e in sentences if s < m.end() and e > m.start()]
    return covering[0][0], covering[-1][1]


def check(questions, corpus_dir, chunk_texts=None) -> list[dict]:
    texts, sentences = {}, {}
    rows = []
    for q in questions:
        row = {"id": q["id"], "question": q["question"], "type": q["type"], "problems": [],
               "passages": [], "other_hits": {}, "not_in_passage": []}
        rows.append(row)
        for a in q["answers"]:
            if len(fold(a)) < MIN_ANSWER_CHARS and not a[:1].isupper():
                row["problems"].append(f"answer {a!r} is too short to match safely")
        if not q["gold"]:
            continue
        spans = []
        for g in q["gold"]:
            if g["file"] not in texts:
                with open(os.path.join(corpus_dir, g["file"]), encoding="utf-8") as f:
                    texts[g["file"]] = f.read()
                sentences[g["file"]] = sentence_spans(texts[g["file"]])
            text = texts[g["file"]]
            span = locate(text, g["quote"], sentences[g["file"]])
            if span is None:
                row["problems"].append(f"gold quote not found in {g['file']}: {g['quote']!r}")
                continue
            passage = _flat(text[span[0]:span[1]])
            fits = chunk_texts is None or any(normalize(passage) in c for c in chunk_texts.get(g["file"], []))
            if not fits:
                row["problems"].append(f"passage does not fit in one chunk: {passage[:80]!r}...")
            spans.append((g["file"], span))
            row["passages"].append({"file": g["file"], "quote": g["quote"], "passage": passage, "fits": fits})
        passages = " ".join(p["passage"] for p in row["passages"])
        for a in q["answers"]:
            if not contains_term(passages, a):
                row["not_in_passage"].append(a)
                continue
            for file in {f for f, _ in spans}:
                text = texts[file]
                folded_hits = []
                for s, e in sentences[file]:
                    if any(file == f and s < se and e > ss for f, (ss, se) in spans):
                        continue
                    if contains_term(text[s:e], a):
                        folded_hits.append(_flat(text[s:e]))
                if folded_hits:
                    row["other_hits"][a] = {"count": len(folded_hits), "examples": folded_hits[:MAX_OTHER_HITS]}
        if row["not_in_passage"]:
            row["problems"].append(f"not in the gold passage: {row['not_in_passage']}")
    return rows


def _chunk_texts(corpus_dir, index_root):
    from RAG.index import CorpusIndex
    from RAG.models import get_embedder
    index = CorpusIndex(corpus_dir, get_embedder(), index_root=index_root)
    index.update()
    by_file = {}
    for c in index.chunks:
        by_file.setdefault(c.file, []).append(normalize(c.text))
    return by_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", default=os.path.join(EVAL_DIR, "corpus"))
    parser.add_argument("--questions", default=os.path.join(EVAL_DIR, "questions.jsonl"))
    parser.add_argument("--index-root", default=os.path.join(EVAL_DIR, ".index"))
    parser.add_argument("--no-chunks", action="store_true", help="skip the fits-in-one-chunk check")
    parser.add_argument("--write", action="store_true",
                        help="replace each quote with its full sentence(s) where that fits in a chunk")
    parser.add_argument("--json", help="also write the report here")
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    chunks = None if args.no_chunks else _chunk_texts(args.corpus, args.index_root)
    rows = check(questions, args.corpus, chunks)

    for row in rows:
        print(f"\n== {row['id']} [{row['type']}] {row['question']}")
        for p in row["passages"]:
            print(f"   passage ({p['file']}{'' if p['fits'] else ', SPANS CHUNKS'}): {p['passage']}")
        for a, hits in row["other_hits"].items():
            print(f"   {a!r} also occurs in {hits['count']} other sentence(s), e.g.:")
            for ex in hits["examples"]:
                print(f"      - {ex[:220]}")
        for problem in row["problems"]:
            print(f"   PROBLEM: {problem}")
    print(f"\n{sum(1 for r in rows if r['problems'])} of {len(rows)} questions have problems; "
          f"{sum(1 for r in rows if r['other_hits'])} have answers occurring elsewhere in the book.")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1, ensure_ascii=False)
    if args.write:
        if any("gold quote not found" in p for r in rows for p in r["problems"]):
            parser.error("fix the missing gold quotes before rewriting")
        by_id = {r["id"]: r for r in rows}
        with open(args.questions, "w", encoding="utf-8") as f:
            for q in questions:
                for g, p in zip(q["gold"], by_id[q["id"]]["passages"]):
                    if p["fits"]:
                        g["quote"] = p["passage"]
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
    return 1 if any(r["problems"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
