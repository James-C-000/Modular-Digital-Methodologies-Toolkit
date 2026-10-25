"""Advanced keyword search page."""
from nicegui import ui

from common.paths import folder_problem, output_folder_problem
from pages.components import (
    FileField, FolderField, JobPanel, hint, missing_dependency, page_header, remember, run_button, saved,
    section, skipped_files, start_job,
)


def keywords_page():
    page_header("Keyword Search", "Count keywords and collect their context across a folder of PDFs")
    try:
        from Advanced_Keyword_Search.advancedKeywordSearchLogic import search_directory
    except ImportError as e:
        missing_dependency(e)
        return

    with section("Folders"):
        src = FolderField("Input folder (PDFs, searched recursively)", "defaults.keywords_input_dir")
        dst = FolderField("Output folder", "defaults.keywords_output_dir")
        hint("Writes one CSV per keyword with its context, an overview CSV, and charts per PDF and in total."
             " Charts of PDFs in sub-folders go in the matching sub-folders of the output folder.")

    with section("Keywords"):
        keywords_text = remember(ui.textarea("Keywords, one per line", value=saved("defaults.keywords_keywords", ""))
                                 .classes("w-full").props("rows=5"), "defaults.keywords_keywords")
        context = remember(ui.number("Context length (words)", value=saved("defaults.keywords_context", 5),
                                     min=1, max=50, precision=0).classes("w-48"), "defaults.keywords_context")

    with section("Filters"):
        basic = remember(ui.checkbox("Basic filter (letters, numbers, hyphens and spaces only)",
                                     value=saved("defaults.keywords_basic_filter", False)),
                         "defaults.keywords_basic_filter")
        hint("Removes other punctuation, symbols and OCR noise before searching. Letters of every language, with"
             " their accents, are kept.")
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
            if summary["files"] and summary.get("hits") == 0:   # not when every PDF was skipped
                ui.label("None of the keywords were found.").classes("text-body2 text-warning")
            skipped_files(summary.get("skipped", []))

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        problem = output_folder_problem(src.value, dst.value, reprocesses_outputs=False) or folder_problem(dst.value)
        if problem:
            return dst.error(problem)
        if not (keywords_text.value or "").strip() and not keyword_file.value:
            return ui.notify("Enter keywords or choose a keyword file.", type="warning")
        folders = (src.value, dst.value)
        options = dict(keywords=keywords_text.value or "", keyword_file=keyword_file.value,
                       filters=filters_text.value or "", filter_file=filter_file.value, basic=bool(basic.value),
                       context_words=int(context.value or 5))

        def work(job):
            summary = search_directory(*folders, **options, on_progress=job.progress, cancel=job.cancel_event)
            for chart in summary["charts"]:
                job.add_image(chart)
            return summary

        start_job("keywords", "Keyword search", work, output_dir=dst.value)

    run_button("Search", start, "keywords")
    JobPanel("keywords", describe=describe)
