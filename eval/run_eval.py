"""Evaluate MDMT's RAG retrieval (and optionally its answers) on eval/questions.jsonl.

    python -m eval.fetch_corpus                       # once
    python -m eval.run_eval                           # retrieval: dense, BM25, hybrid, hybrid+rerank
    python -m eval.run_eval --no-rerank --check eval/baseline.json   # the CI regression
    python -m eval.run_eval --llm models/Qwen3.5-2B-Q4_K_M.gguf      # + answers and citations

Retrieval metrics are recall@k (a relevant chunk in the top k) and MRR@20 over
the answerable questions.  With --llm, each question is asked in a fresh
conversation and scored for short-answer accuracy, citation validity (cited
chunks that contain a gold passage) and not-found behaviour.
"""
import argparse
import json
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.fetch_corpus import EVAL_DIR, corpus_hashes, load_questions  # noqa: E402
from eval.metrics import answer_matches, first_relevant_rank, is_relevant, mrr, recall_at  # noqa: E402

KS = (1, 3, 6, 20)
DEPTH = 20  # candidates kept per mode (the reranker sees the hybrid top 20, as in RagSettings)


def _ranked(index, ids):
    return [(index.chunks[i].file, index.chunks[i].text) for i in ids]


def retrieval_runs(index, questions, rerank):
    """{mode: [rank of first relevant chunk or None, per question]} and per-question detail."""
    from RAG.search import bm25_tokens, dense_top
    reranker = None
    if rerank:
        from RAG.models import get_reranker
        reranker = get_reranker()
    modes = ["dense", "bm25", "hybrid"] + (["hybrid+rerank"] if rerank else [])
    ranks, detail, rerank_s = {m: [] for m in modes}, [], 0.0
    for q in questions:
        dense = [i for i, _s in dense_top(index.embeddings, index.embedder.embed_query(q["question"]), DEPTH)]
        lexical = [i for i, _s in index.bm25.top(bm25_tokens(q["question"]), DEPTH)]
        hybrid = [h.index for h in index.search(q["question"], k=DEPTH)]
        lists = {"dense": dense, "bm25": lexical, "hybrid": hybrid}
        if reranker is not None:
            t = time.perf_counter()
            scores = reranker.score(q["question"], [index.chunks[i].text for i in hybrid])
            rerank_s += time.perf_counter() - t
            lists["hybrid+rerank"] = [i for _s, i in sorted(zip(scores, hybrid), key=lambda p: -float(p[0]))]
        row = {"id": q["id"]}
        for mode in modes:
            r = first_relevant_rank(_ranked(index, lists[mode]), q["gold"])
            ranks[mode].append(r)
            row[mode] = r
        detail.append(row)
    return ranks, detail, rerank_s


def summarize_ranks(ranks):
    return {mode: {**{f"recall@{k}": round(recall_at(r, k), 3) for k in KS}, "mrr": round(mrr(r), 3)}
            for mode, r in ranks.items()}


def answer_run(args, questions):
    from RAG.session import RagSession, RagSettings
    settings = RagSettings(args.corpus, args.llm, n_ctx=args.context_window, rerank=not args.no_rerank,
                           n_gpu_layers=args.gpu_layers)
    session = RagSession(settings, index_root=args.index_root)
    session.build_index()
    rows = []
    try:
        for q in questions:
            session.reset_conversation()
            a = session.ask(q["question"])
            valid = [is_relevant(c.chunk.file, c.chunk.text, q["gold"]) for c in a.citations]
            rows.append({
                "id": q["id"], "type": q["type"], "answer": a.text, "not_found": a.not_found,
                "correct": (a.not_found if q["type"] == "unanswerable" else answer_matches(a.text, q["answers"])),
                "citations": len(a.citations), "valid_citations": sum(valid),
                "dropped_citations": len(a.dropped_citations), "seconds": round(sum(a.timings.values()), 2),
            })
            print(f"  {q['id']}: {'ok ' if rows[-1]['correct'] else 'MISS'} {a.text[:90]!r}", file=sys.stderr)
    finally:
        session.close()
    answerable = [r for r in rows if r["type"] != "unanswerable"]
    unanswerable = [r for r in rows if r["type"] == "unanswerable"]
    cited = [r for r in answerable if r["citations"]]
    return rows, {
        "short_answer_accuracy": round(sum(r["correct"] for r in answerable) / len(answerable), 3),
        "answers_with_a_citation": round(len(cited) / len(answerable), 3),
        "answers_citing_a_gold_passage": round(sum(1 for r in answerable if r["valid_citations"]) / len(answerable), 3),
        "citation_precision": round(sum(r["valid_citations"] for r in cited) / max(1, sum(r["citations"] for r in cited)), 3),
        "out_of_range_citations": sum(r["dropped_citations"] for r in rows),
        "false_not_found": sum(1 for r in answerable if r["not_found"]),
        "unanswerable_refused": f"{sum(r['not_found'] for r in unanswerable)}/{len(unanswerable)}",
        "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2),
    }


def markdown(results) -> str:
    lines = ["| Retrieval | " + " | ".join(f"Recall@{k}" for k in KS) + " | MRR@20 |",
             "|---|" + "---:|" * (len(KS) + 1)]
    for mode, m in results["retrieval"].items():
        lines.append(f"| {mode} | " + " | ".join(f"{m[f'recall@{k}']:.2f}" for k in KS) + f" | {m['mrr']:.2f} |")
    for group, by_mode in results.get("retrieval_by_type", {}).items():
        lines.append(f"| hybrid{'+rerank' if 'hybrid+rerank' in by_mode else ''}, {group} only | "
                     + " | ".join(f"{list(by_mode.values())[-1][f'recall@{k}']:.2f}" for k in KS)
                     + f" | {list(by_mode.values())[-1]['mrr']:.2f} |")
    if "answers" in results:
        lines += ["", "| Answers | |", "|---|---:|"]
        lines += [f"| {k.replace('_', ' ')} | {v} |" for k, v in results["answers"].items()]
    return "\n".join(lines)


def check(results, baseline_path) -> list[str]:
    """Regressions: any baseline metric that dropped by more than its tolerance."""
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    tol, failures = baseline.get("tolerance", 0.05), []
    for mode, metrics in baseline["retrieval"].items():
        for name, floor in metrics.items():
            got = results["retrieval"].get(mode, {}).get(name)
            if got is None or got < floor - tol:
                failures.append(f"{mode} {name}: {got} < baseline {floor} - {tol}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate MDMT RAG retrieval and answers",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--corpus", default=os.path.join(EVAL_DIR, "corpus"))
    parser.add_argument("--questions", default=os.path.join(EVAL_DIR, "questions.jsonl"))
    parser.add_argument("--index-root", default=os.path.join(EVAL_DIR, ".index"))
    parser.add_argument("--out", default=os.path.join(EVAL_DIR, "results"), help="folder for results JSON/MD")
    parser.add_argument("--no-rerank", action="store_true", help="skip the hybrid+rerank run")
    parser.add_argument("--check", metavar="BASELINE", help="fail if retrieval falls below this baseline")
    parser.add_argument("--llm", help="also evaluate answers with this Qwen GGUF model")
    parser.add_argument("--context-window", type=int, default=8192)
    parser.add_argument("--gpu-layers", type=int, default=0)
    args = parser.parse_args(argv)

    from RAG.index import CorpusIndex
    from RAG.models import get_embedder
    questions = load_questions(args.questions)
    answerable = [q for q in questions if q["type"] != "unanswerable"]

    t = time.perf_counter()
    index = CorpusIndex(args.corpus, get_embedder(), index_root=args.index_root)
    report = index.update()
    index_s = time.perf_counter() - t
    if report.failed:
        parser.error(f"could not index {report.failed}")
    print(f"Indexed {report.chunks} chunks in {index_s:.0f}s", file=sys.stderr)

    ranks, detail, rerank_s = retrieval_runs(index, answerable, rerank=not args.no_rerank)
    results = {
        "questions": len(questions), "answerable": len(answerable),
        "reviewed": sum(1 for q in questions if q.get("reviewed")),
        "chunks": report.chunks, "corpus_sha256": corpus_hashes(args.corpus),
        "retrieval": summarize_ranks(ranks),
        "retrieval_by_type": {},
        "rerank_seconds_per_question": round(rerank_s / len(answerable), 2) if rerank_s else None,
        "per_question": detail,
    }
    for group in ("factual", "paraphrase", "cross-lingual"):
        keep = [i for i, q in enumerate(answerable) if q["type"] == group]
        if keep:
            results["retrieval_by_type"][group] = summarize_ranks(
                {m: [r[i] for i in keep] for m, r in ranks.items() if m.startswith("hybrid")})
    if args.llm:
        results["answer_rows"], results["answers"] = answer_run(args, questions)
        results["llm"] = os.path.basename(args.llm)

    os.makedirs(args.out, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(args.out, f"results-{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    table = markdown(results)
    with open(os.path.join(args.out, f"results-{stamp}.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(table)
    if results["reviewed"] < len(questions):
        print(f"\nNote: {len(questions) - results['reviewed']} of {len(questions)} questions are unreviewed drafts.",
              file=sys.stderr)

    if args.check:
        failures = check(results, args.check)
        for failure in failures:
            print("REGRESSION:", failure, file=sys.stderr)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
