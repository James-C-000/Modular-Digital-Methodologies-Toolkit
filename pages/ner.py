"""Named Entity Recognition page."""
from nicegui import ui

from common.paths import folder_problem
from pages.components import (
    FolderField, JobPanel, hint, page_header, run_button, section, skipped_files, start_job,
)


def ner_page():
    page_header("Named Entities", "Find people, organizations, places and dates in documents")
    from NLP.ner_onnx import DEFAULT_NER_MODEL, NER_MODELS, is_model_installed
    info = NER_MODELS[DEFAULT_NER_MODEL]

    with section("Folder"):
        src = FolderField("Input folder (.txt and .pdf, searched recursively)", "defaults.ner_input_dir")
        hint("Writes a highlighted copy of each document, as HTML, next to it, and a summary report into the input"
             " folder.")
        if not is_model_installed(DEFAULT_NER_MODEL):
            hint(f"The {info['name']} model ({info['size']}) downloads on first use, or from the Downloads page.")

    def describe(job):
        summary = job.result or {}
        if not summary:
            return
        ui.label(f"{summary['files']} of {summary['total']} file(s) analysed.").classes("text-body2")
        skipped_files(summary.get("skipped", []))
        open_report_button(summary["summary"])

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        folder = src.value

        def work(job):
            from NLP.named_entity_recognition import main as ner_main
            job.progress(0, 0, "Loading the NER model...")
            return ner_main(folder, on_progress=job.progress, cancel=job.cancel_event)

        start_job("ner", "Named entities", work, output_dir=folder)

    run_button("Find entities", start, "ner")
    JobPanel("ner", describe=describe)


def open_report_button(path):
    from common.opener import open_external
    ui.button("Open summary report", icon="article", on_click=lambda: open_external(path)).props("flat dense")
