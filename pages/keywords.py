"""Advanced keyword search page."""
from nicegui import ui

from common.paths import folder_problem, output_folder_problem
from pages.components import (
    FileField, FolderField, JobPanel, hint, missing_dependency, page_header, remember, run_button, saved,
    section, start_job,
)


def keywords_page():
    page_header("Keyword Search", "Count keywords and collect their context across a folder of PDFs")
    try:
        from Advanced_Keyword_Search.advancedKeywordSearchLogic import core_logic
    except ImportError as e:
        missing_dependency(e)
        return

    with section("Folders"):
        src = FolderField("PDF folder", "defaults.keywords_input_dir")
        dst = FolderField("Output folder", "defaults.keywords_output_dir")
        hint("Writes one CSV per keyword with its context, an overview CSV, and charts per PDF and in total.")

    with section("Keywords"):
        keywords_text = remember(ui.textarea("Keywords, one per line", value=saved("defaults.keywords_keywords", ""))
                                 .classes("w-full").props("rows=5"), "defaults.keywords_keywords")
        context = remember(ui.number("Context length (words)", value=saved("defaults.keywords_context", 5),
                                     min=1, max=50, precision=0).classes("w-48"), "defaults.keywords_context")

    with section("Filters"):
        basic = remember(ui.checkbox("Basic filter (letters and numbers only)",
                                     value=saved("defaults.keywords_basic_filter", False)),
                         "defaults.keywords_basic_filter")
        hint("Strips every character except letters, numbers and spaces before searching; useful for OCR noise.")
        filters_text = remember(ui.textarea("Characters to remove, one group per line",
                                            value=saved("defaults.keywords_filters", ""))
                                .classes("w-full").props("rows=3"), "defaults.keywords_filters")
        hint("Every character listed here is removed from the text before searching.")

    with ui.expansion("Or load keywords and filters from files").classes("w-full"):
        keyword_file = FileField("Keyword file (.txt)", "defaults.keywords_keyword_file", [".txt"], "Text files")
        filter_file = FileField("Filter file (.txt)", "defaults.keywords_filter_file", [".txt"], "Text files")

    def describe(job):
        summary = job.result or {}
        if summary:
            ui.label(f"{summary['files']} of {summary['total']} PDF(s) searched.").classes("text-body2")

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        problem = output_folder_problem(src.value, dst.value, reprocesses_outputs=False) or folder_problem(dst.value)
        if problem:
            return dst.error(problem)
        if not (keywords_text.value or "").strip() and not keyword_file.value:
            return ui.notify("Enter keywords or choose a keyword file.", type="warning")
        args = (str(int(context.value or 5)), 1 if basic.value else 0, src.value, dst.value, keyword_file.value,
                keywords_text.value or "", filter_file.value, filters_text.value or "")

        def work(job):
            errors = []
            summary = core_logic(*args, on_error=errors.append, on_progress=job.progress, cancel=job.cancel_event)
            if errors:
                raise RuntimeError(errors[0].replace("ERROR: ", "").replace("\n", " "))
            for chart in summary["charts"]:
                job.add_image(chart)
            return summary

        start_job("keywords", "Keyword search", work, output_dir=dst.value)

    run_button("Search", start, "keywords")
    JobPanel("keywords", describe=describe)
