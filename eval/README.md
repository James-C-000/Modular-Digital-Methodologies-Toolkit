# RAG evaluation

Measures how well MDMT's RAG chat finds and uses the right passages.

**Status: the question set is a draft.** Every question in `questions.jsonl` has
`"reviewed": false` until James has checked it. Results are not published (in
`docs/` or the main README) before then.

## Corpus

Six public-domain books from Project Gutenberg, listed in `corpus.json`:
Douglass's *Narrative*, Paine's *Common Sense*, Franklin's *Autobiography* and
Wollstonecraft's *Vindication* in English, Voltaire's *Candide* in French, and
Kafka's *Die Verwandlung* in German. They are downloaded, not committed:

    python -m eval.fetch_corpus

The script removes the Gutenberg header and license footer and checks that every
gold quote still occurs in the text, so a re-edited Gutenberg file fails loudly.

## Questions

`questions.jsonl`, one JSON object per line:

| Field | Meaning |
|---|---|
| `id` | stable identifier |
| `lang` | language of the question |
| `type` | `factual` (shares words with the passage), `paraphrase` (says it differently), `cross-lingual` (English question, French or German passage) or `unanswerable` (not in the corpus) |
| `question` | what is asked |
| `gold` | `{file, quote}` pairs: a retrieved chunk is relevant if it is from `file` and contains `quote` (case, whitespace and quote style ignored) |
| `answers` | accepted short answers: an answer is correct if it contains any of them (accents ignored) |
| `reviewed` | set to `true` once a person has checked the question, gold passage and answers |

## Running

    python -m eval.run_eval                     # dense, BM25, hybrid, hybrid+rerank
    python -m eval.run_eval --no-rerank         # skip the 588 MB reranker
    python -m eval.run_eval --llm models/Qwen3.5-2B-Q4_K_M.gguf   # + answer quality

Retrieval is scored with recall@k (a relevant chunk among the top k; the chat
gives the model the top 6) and MRR@20, over the answerable questions. With
`--llm`, every question is asked in a fresh conversation and scored for
short-answer accuracy, citation validity (cited chunks that contain a gold
passage), out-of-range citations, and whether unanswerable questions get the
"not found" reply.

Results go to `eval/results/` (not committed) as JSON and a Markdown table,
together with the sha256 of each corpus file.

## CI

The Tests workflow runs `python -m eval.run_eval --no-rerank --check
eval/baseline.json` on Linux and fails if a retrieval metric drops more than
0.05 below `baseline.json`.
