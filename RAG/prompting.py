"""Prompts and answer post-processing for grounded RAG answers.

- Context chunks are numbered [1]..[n] with their file and page.
- The model must cite chunks as [n]; citations are validated afterwards and
  out-of-range numbers removed.
- If the documents do not contain the answer the model must reply with
  NOT_FOUND, which the UI shows as a clean "not found" message.
- Follow-up questions are rewritten into standalone search queries using the
  recent conversation, before retrieval.
"""
import re

NOT_FOUND = "I could not find this in the documents."

SYSTEM_PROMPT = f"""You are a careful research assistant. Answer the question using only the numbered documents provided.
Rules:
- After each statement, cite the documents that support it with their numbers in square brackets, e.g. [2] or [1][3].
- Cite only document numbers that appear in the provided list.
- Do not use outside knowledge and do not invent quotations, names, dates or numbers.
- If the documents do not contain the answer, reply exactly: {NOT_FOUND}
- Be concise and answer in the language of the question."""

# Repeated right after the question: small models (Qwen3.5-0.8B) follow it far
# more reliably than the system prompt alone.
CITE_REMINDER = ("Answer concisely and put the number of each supporting document in square brackets, "
                 f"like [1]. If the documents do not contain the answer, reply exactly: {NOT_FOUND}")

REWRITE_PROMPT = """Rewrite the user's latest question as a single standalone search query that can be understood without the conversation. Resolve pronouns and references ("he", "that ship", "the same year") using the conversation. Keep names, dates and other specific terms. Reply with the query only."""


def source_label(chunk) -> str:
    return f"{chunk.file}, page {chunk.page}" if chunk.page else chunk.file


def format_context(chunks) -> str:
    return "\n\n".join(f"[{i}] {source_label(c)}\n{c.text.strip()}" for i, c in enumerate(chunks, 1))


_CITATION = re.compile(r"\[(\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-–]\s*\d+)?)*)\]")


def parse_citations(answer: str, n_sources: int):
    """Normalise citations to [n][m], drop invalid numbers.

    Returns (clean answer, valid numbers in first-appearance order, dropped numbers).
    """
    cited, dropped = [], []

    def replace(match):
        numbers = []
        for part in re.split(r"\s*,\s*", match.group(1)):
            if re.search(r"[-–]", part):
                a, b = (int(x) for x in re.split(r"\s*[-–]\s*", part))
                numbers.extend(range(a, b + 1) if b >= a and b - a < 50 else [a, b])
            else:
                numbers.append(int(part))
        keep = []
        for n in numbers:
            if 1 <= n <= n_sources:
                if n not in keep:
                    keep.append(n)
                if n not in cited:
                    cited.append(n)
            elif n not in dropped:
                dropped.append(n)
        return "".join(f"[{n}]" for n in keep)

    text = _CITATION.sub(replace, answer)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)   # "Also [0]." -> "Also."
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text, cited, dropped


def is_not_found(answer: str) -> bool:
    return answer.strip().lower().startswith(NOT_FOUND.lower().rstrip("."))


def _strip_citations(text: str) -> str:
    return re.sub(r"\s*" + _CITATION.pattern, "", text)


def history_window(history, budget_tokens: int, count_tokens) -> list:
    """The most recent (question, answer) turns that fit in *budget_tokens*."""
    kept, used = [], 0
    for question, answer in reversed(history):
        cost = count_tokens(question) + count_tokens(answer)
        if used + cost > budget_tokens:
            break
        kept.insert(0, (question, answer))
        used += cost
    return kept


def answer_messages(question: str, chunks, history=()) -> list[dict]:
    """Chat messages for the final answer (history already trimmed to budget)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, a in history:
        # Earlier answers cite an earlier document list; drop their [n] marks.
        messages += [{"role": "user", "content": q}, {"role": "assistant", "content": _strip_citations(a)}]
    messages.append({"role": "user", "content":
                     f"Documents:\n{format_context(chunks)}\n\nQuestion: {question}\n\n{CITE_REMINDER}"})
    return messages


def rewrite_messages(question: str, history, max_turns: int = 3) -> list[dict]:
    """Chat messages asking the LLM for a standalone retrieval query."""
    lines = []
    for q, a in list(history)[-max_turns:]:
        lines += [f"User: {q}", f"Assistant: {_strip_citations(a)}"]
    conversation = "\n".join(lines)
    return [{"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": f"Conversation:\n{conversation}\n\nLatest question: {question}"}]


def split_thinking(text: str, started_in_thinking: bool = False) -> tuple[str, str]:
    """Split model output into (reasoning, answer) around <think>...</think>."""
    if not started_in_thinking:
        m = re.match(r"\s*<think>", text)
        if not m:
            return "", text.strip()
        text = text[m.end():]
    if "</think>" in text:
        thinking, answer = text.split("</think>", 1)
        return thinking.strip(), answer.strip()
    return text.strip(), ""
