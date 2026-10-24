#!/usr/bin/env python3
"""Headless command-line interface to MDMT's RAG system.

Interactive chat:
    python -m RAG.qwen_rag --documents ./docs --llm ./models/Qwen3.5-2B-Q4_K_M.gguf

Scripting (one answer per --question; JSON lines with --json):
    python -m RAG.qwen_rag --documents ./docs --llm model.gguf --question "Who ...?" --json

The index is stored in MDMT's app data folder and updated incrementally.
"""
import argparse
import json
import os
import sys

if __package__ in (None, ""):  # allow "python RAG/qwen_rag.py"
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from RAG.session import RagSession, RagSettings  # noqa: E402


def _answer_record(question, answer) -> dict:
    return {
        "question": question,
        "query": answer.query,
        "answer": answer.text,
        "not_found": answer.not_found,
        "cut_off": answer.cut_off,
        "cut_off_while_thinking": answer.cut_off_while_thinking,
        "citations": [{"n": c.number, "file": c.chunk.file, "page": c.chunk.page,
                       "start": c.chunk.start, "end": c.chunk.end} for c in answer.citations],
        "context": [{"n": c.number, "file": c.chunk.file, "page": c.chunk.page, "score": c.score}
                    for c in answer.context],
        "dropped_citations": answer.dropped_citations,
        "timings": answer.timings,
    }


def _print_answer(answer):
    print(f"\nAssistant: {answer.text}")
    if answer.cut_off:
        from RAG.session import THINKING_CONTEXT
        where = "while reasoning, before answering" if answer.cut_off_while_thinking else "before finishing"
        print(f"  (Ran out of room {where}. Try --context-window {THINKING_CONTEXT}, or leave out"
              " --enable-thinking if there is not enough memory.)")
    for c in answer.citations:
        page = f", page {c.chunk.page}" if c.chunk.page else ""
        print(f"  [{c.number}] {c.chunk.file}{page}")
    print(f"  ({sum(answer.timings.values()):.1f}s)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="MDMT RAG chat over a folder of documents",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--documents", required=True, help="folder of documents to index")
    parser.add_argument("--llm", required=True, help="Qwen 3.5 GGUF model file")
    parser.add_argument("--question", action="append", help="answer this question and exit (repeatable)")
    parser.add_argument("--json", action="store_true", help="print answers as JSON lines")
    parser.add_argument("--context-window", type=int, default=None,
                        help="tokens of context (default 8192, or 32768 with --enable-thinking)")
    parser.add_argument("--top-k", type=int, default=6, help="chunks given to the model")
    parser.add_argument("--no-rerank", action="store_true", help="skip the cross-encoder reranker")
    parser.add_argument("--enable-thinking", action="store_true", help="let the model reason first")
    parser.add_argument("--gpu-layers", type=int, default=0, help="layers to offload to the GPU (-1 = all)")
    parser.add_argument("--threads", type=int, default=None)
    args = parser.parse_args(argv)

    if not os.path.isdir(args.documents):
        parser.error(f"documents folder not found: {args.documents}")
    if not os.path.isfile(args.llm):
        parser.error(f"model file not found: {args.llm}")

    from RAG.session import THINKING_CONTEXT
    n_ctx = args.context_window or (THINKING_CONTEXT if args.enable_thinking else 8192)
    settings = RagSettings(documents_dir=args.documents, llm_path=args.llm, n_ctx=n_ctx,
                           top_k=args.top_k, rerank=not args.no_rerank, enable_thinking=args.enable_thinking,
                           n_gpu_layers=args.gpu_layers, threads=args.threads)
    session = RagSession(settings)
    if session.notice:
        print(session.notice, file=sys.stderr)
    log = sys.stderr if args.json else sys.stdout
    report = session.build_index(lambda done, total, name: print(
        f"\rIndexing {done}/{total} {name[:60]:<60}", end="", file=log, flush=True))
    print(f"\nIndexed {report.chunks} chunks ({len(report.added)} new, {len(report.changed)} changed, "
          f"{len(report.removed)} removed, {report.unchanged} unchanged).", file=log)
    for rel, err in report.failed:
        print(f"  skipped {rel}: {err}", file=log)

    try:
        if args.question:
            for question in args.question:
                answer = session.ask(question)
                if args.json:
                    print(json.dumps(_answer_record(question, answer), ensure_ascii=False), flush=True)
                else:
                    print(f"\nYou: {question}")
                    _print_answer(answer)
            return 0

        print("Type a question; 'reset' forgets the conversation, 'reindex' rescans the folder, 'exit' quits.")
        while True:
            try:
                question = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not question:
                continue
            if question.lower() in ("exit", "quit"):
                return 0
            if question.lower() == "reset":
                session.reset_conversation()
                continue
            if question.lower() == "reindex":
                report = session.build_index()
                print(f"Indexed {report.chunks} chunks.")
                continue
            _print_answer(session.ask(question, on_token=lambda kind, text: print(
                text, end="", flush=True) if kind == "answer" else None))
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
