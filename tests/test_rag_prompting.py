from RAG.chunking import Chunk
from RAG.prompting import (
    CITE_REMINDER,
    NOT_FOUND,
    answer_messages,
    format_context,
    history_window,
    is_not_found,
    not_found_remainder,
    parse_citations,
    rewrite_messages,
    split_thinking,
)

CHUNKS = [Chunk("The brig Endeavour arrived from Lisbon.", "ledger.pdf", 3, 0, 39, 0),
          Chunk("The mill flooded in 1751.", "notes/mill.txt", None, 0, 25, 0)]


def words(text):
    return len(text.split())


def test_context_is_numbered_with_file_and_page():
    ctx = format_context(CHUNKS)
    assert ctx.startswith("[1] ledger.pdf, page 3\nThe brig Endeavour")
    assert "[2] notes/mill.txt\nThe mill flooded" in ctx


class TestCitations:
    def test_valid_citations_in_first_appearance_order(self):
        text, cited, dropped = parse_citations("Lisbon [2]. The brig sailed [1][2].", 2)
        assert cited == [2, 1] and dropped == [] and text == "Lisbon [2]. The brig sailed [1][2]."

    def test_out_of_range_citations_are_removed(self):
        text, cited, dropped = parse_citations("It came from Lisbon [1][7]. Also [0].", 2)
        assert cited == [1] and dropped == [7, 0]
        assert text == "It came from Lisbon [1]. Also."

    def test_grouped_and_ranged_citations(self):
        text, cited, _ = parse_citations("See [1, 2] and [1-3].", 3)
        assert cited == [1, 2, 3]
        assert text == "See [1][2] and [1][2][3]."

    def test_partially_invalid_group(self):
        text, cited, dropped = parse_citations("See [2, 9].", 3)
        assert text == "See [2]." and cited == [2] and dropped == [9]

    def test_brackets_that_are_not_citations_are_left_alone(self):
        text, cited, _ = parse_citations("The year [sic] and a list [a].", 3)
        assert text == "The year [sic] and a list [a]." and cited == []


def test_not_found_detection():
    assert is_not_found(NOT_FOUND)
    assert is_not_found("  " + NOT_FOUND.lower())
    assert not is_not_found("Lisbon [1].")


def test_paraphrased_refusals_are_detected():
    # Seen from Qwen3.5-0.8B in eval/ runs.
    for answer in [
        "Based on the provided documents, none of them mention who painted the ceiling of the Sistine Chapel.",
        "Based on the provided documents, there is no mention of the invention of an electric telegraph.",
        "Based on the provided documents, no specific information is given regarding who painted it.\n\n[1] discusses Rousseau.",
        "The documents do not contain this information.",
        "Les documents ne mentionnent pas qui a peint ce plafond.",
        "Je n'ai pas trouvé cette information dans les documents.",
        "Aucune information à ce sujet dans les documents.",
        "Die Dokumente enthalten keine Informationen darüber.",
        "Das wird in den Dokumenten nicht erwähnt.",
    ]:
        assert is_not_found(answer), answer


def test_answers_with_content_are_not_refusals():
    for answer in [
        "Lisbon [1].",
        "The documents do not mention his age, but he was born in Tuckahoe [1].",   # cited: real content
        "He was born in Tuckahoe [1]. The documents do not mention the year.",       # refusal not first
        "Gregor's father did not throw anything at him; an apple grazed his back [3].",
        "Not found anywhere else, the Junto met on Friday evenings [2].",
    ]:
        assert not is_not_found(answer), answer


def test_not_found_remainder_keeps_anything_beyond_the_stock_reply():
    assert not_found_remainder(NOT_FOUND) == ""
    assert not_found_remainder(NOT_FOUND + " The mill is mentioned in [2].") == "The mill is mentioned in [2]."
    para = "The documents do not contain this information."
    assert not_found_remainder(para) == para


def test_answer_prompt_carries_question_context_rules_and_history():
    history = [("Where did the brig come from?", "Lisbon [1].")]
    msgs = answer_messages("When did it arrive?", CHUNKS, history)
    assert msgs[0]["role"] == "system" and "square brackets" in msgs[0]["content"]
    assert NOT_FOUND in msgs[0]["content"]
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]
    # Old answers' [n] refer to an earlier document list: they must not confuse the model.
    assert msgs[2]["content"] == "Lisbon."
    assert msgs[-1]["content"].startswith("Documents:\n[1] ledger.pdf, page 3")
    assert "Question: When did it arrive?\n\n" in msgs[-1]["content"]
    assert msgs[-1]["content"].endswith(CITE_REMINDER)


class TestRewrite:
    def test_rewrite_prompt_includes_recent_history_and_the_follow_up(self):
        history = [("Who was the harbour master in 1788?", "Josiah Penrose [1]."),
                   ("What duty did he record?", "£14 6s [1].")]
        msgs = rewrite_messages("And for the Swift?", history)
        assert msgs[0]["role"] == "system" and "standalone" in msgs[0]["content"]
        user = msgs[-1]["content"]
        assert "Josiah Penrose" in user and "£14 6s" in user and user.rstrip().endswith("And for the Swift?")

    def test_answers_in_the_rewrite_prompt_have_no_citation_marks(self):
        msgs = rewrite_messages("And then?", [("Q?", "Lisbon [1][2].")])
        assert "[1]" not in msgs[-1]["content"]


def test_history_window_keeps_the_most_recent_turns_within_budget():
    history = [(f"question {i} " + "x " * 20, f"answer {i} " + "y " * 20) for i in range(10)]
    window = history_window(history, budget_tokens=100, count_tokens=words)
    assert window == history[-2:]
    assert history_window(history, budget_tokens=5, count_tokens=words) == []
    assert history_window([], 100, words) == []


def test_split_thinking_handles_streamed_fragments():
    pieces = ["<thi", "nk>Let me ", "check.</th", "ink>\n\nLisbon", " [1]."]
    thinking, answer = split_thinking("".join(pieces))
    assert thinking == "Let me check." and answer == "Lisbon [1]."
    # The thinking-mode prompt already opens <think>, so output may start inside it.
    assert split_thinking("Reasoning here.</think>Answer.", started_in_thinking=True) == ("Reasoning here.", "Answer.")
    assert split_thinking("Still reasoning", started_in_thinking=True) == ("Still reasoning", "")
    assert split_thinking("Plain answer.") == ("", "Plain answer.")
