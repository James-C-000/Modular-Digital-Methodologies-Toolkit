"""Co-word analysis page."""
from nicegui import ui

from common.paths import folder_problem
from pages.components import (
    FolderField, JobPanel, hint, page_header, remember, run_button, saved, section, start_job,
)
from pages.ner import open_report_button


def cowords_page():
    page_header("Co-Words", "Word co-occurrence networks that reveal how concepts relate")
    from NLP.text_utils import STOPWORD_LANGUAGES, parse_custom_stopwords

    with section("Folder"):
        src = FolderField("Input folder (.txt and .pdf, searched recursively)", "defaults.cowords_input_dir")
        hint("Writes a report and a network graph per document, and a summary report, into the input folder.")

    with section("Words to ignore"):
        options = {"": "None (keep every word)"}
        options.update({code: f"{name} — {source}" for code, (name, source) in STOPWORD_LANGUAGES.items()})
        stop_lang = remember(ui.select(options, label="Stopword list", with_input=True,
                                       value=saved("defaults.cowords_stopwords", "en")).classes("w-full"),
                             "defaults.cowords_stopwords")
        hint("Snowball lists contain only function words (the, and, of...). \"Extended\" lists, used for languages"
             " Snowball does not cover, are broader and may remove some content words.")
        custom = remember(ui.textarea("Additional words to ignore (optional)",
                                      value=saved("defaults.cowords_custom_stopwords", ""))
                          .classes("w-full").props("rows=2"), "defaults.cowords_custom_stopwords")

    def describe(job):
        summary = job.result or {}
        if summary:
            ui.label(f"{summary['files']} of {summary['total']} file(s) analysed.").classes("text-body2")
            open_report_button(summary["summary"])

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        folder, lang = src.value, stop_lang.value or None
        extra = parse_custom_stopwords(custom.value)

        def work(job):
            from NLP.co_word_analysis import main as co_word_main
            summary = co_word_main(folder, stopword_language=lang, extra_stopwords=extra,
                                   on_progress=job.progress, cancel=job.cancel_event)
            for image in summary["images"]:
                job.add_image(image)
            return summary

        start_job("cowords", "Co-words", work, output_dir=folder)

    run_button("Run analysis", start, "cowords")
    JobPanel("cowords", describe=describe)
