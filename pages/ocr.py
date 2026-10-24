"""OCR processing page."""
from nicegui import ui

from common.paths import folder_problem, output_folder_problem
from pages.components import (
    FolderField, JobPanel, file_results, hint, missing_dependency, needs_download, page_header, remember,
    run_button, saved, section, start_job,
)


def ocr_page():
    page_header("OCR", "Add a searchable text layer to scanned PDFs (Tesseract, runs offline)")
    try:
        from OCR.ocr_logic import (
            GHOSTSCRIPT_DOWNLOAD_URL, TESSERACT_LANGUAGES, find_ghostscript, run_ocr_batch,
        )
        from OCR.tessdata import installed_languages
    except ImportError as e:
        missing_dependency(e)
        return

    installed = installed_languages()
    available_langs = [name for name, code in TESSERACT_LANGUAGES.items() if code in installed]
    has_osd = "osd" in installed
    ghostscript = find_ghostscript()
    if not available_langs:
        needs_download("No OCR languages installed", "Download at least one language from the Downloads page.")
        return

    with section("Folders"):
        src = FolderField("Input folder (PDFs, searched recursively)", "defaults.ocr_input_dir")
        dst = FolderField("Output folder", "defaults.ocr_output_dir", must_exist=False)
        hint("The output folder keeps the input's sub-folders. It is created if it does not exist.")

    with section("Languages"):
        langs = [n for n in saved("defaults.ocr_languages", ["English"]) if n in available_langs]
        lang_select = remember(ui.select(available_langs, multiple=True, label="Languages in the documents",
                                         value=langs or available_langs[:1]).classes("w-full").props("use-chips"),
                               "defaults.ocr_languages")
        with ui.row().classes("items-center gap-1"):
            hint("Select every language that appears in your documents.")
            ui.button("More languages", icon="download", on_click=lambda: ui.navigate.to("/downloads")) \
                .props("flat dense no-caps size=sm")

    with section("Options"):
        with ui.row().classes("w-full"):
            deskew = remember(ui.checkbox("Deskew", value=saved("defaults.ocr_deskew", False)), "defaults.ocr_deskew")
            # Disabled Quasar controls ignore the mouse, so explanatory tooltips go on wrapper elements.
            with ui.element("div") as rotate_wrap:
                rotate = remember(ui.checkbox("Rotate pages", value=has_osd and saved("defaults.ocr_rotate", False)),
                                  "defaults.ocr_rotate")
            redo_ocr = remember(ui.checkbox("Redo OCR", value=saved("defaults.ocr_redo", False)), "defaults.ocr_redo")
            with ui.element("div") as pdfa_wrap:
                pdfa = remember(ui.checkbox("PDF/A output", value=bool(ghostscript) and saved("defaults.ocr_pdfa", False)),
                                "defaults.ocr_pdfa")
            extract_text = remember(ui.checkbox("Extract text (.txt)", value=saved("defaults.ocr_extract_text", False)),
                                    "defaults.ocr_extract_text")
        if not has_osd:
            rotate.disable()
            rotate_wrap.tooltip("Needs the 'osd' data file — install it from the Downloads page.")
        if not ghostscript:
            pdfa.disable()
            pdfa_wrap.tooltip("PDF/A output needs Ghostscript, which is not installed (see below).")
            with ui.row().classes("items-center gap-1 text-caption mdmt-muted"):
                ui.label("PDF/A output requires Ghostscript (not bundled with MDMT). Install it from")
                ui.link("ghostscript.com", GHOSTSCRIPT_DOWNLOAD_URL, new_tab=True)
                ui.label("and restart MDMT.")
        deskew.bind_enabled_from(redo_ocr, "value", backward=lambda v: not v)
        redo_ocr.bind_enabled_from(deskew, "value", backward=lambda v: not v)
        with ui.row().classes("w-full items-center").bind_visibility_from(rotate, "value"):
            ui.label("Rotation sensitivity:")
            rotate_threshold = remember(ui.radio({2: "High", 6: "Normal", 15: "Low"},
                                                 value=saved("defaults.ocr_rotate_threshold", 6)).props("inline"),
                                        "defaults.ocr_rotate_threshold")

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        problem = output_folder_problem(src.value, dst.value, reprocesses_outputs=True)
        if problem:
            return dst.error(problem)
        if not lang_select.value:
            return ui.notify("Select at least one language.", type="warning")
        options = dict(input_dir=src.value, output_dir=dst.value, language_names=list(lang_select.value),
                       deskew=deskew.value, rotate_pages=rotate.value, rotate_threshold=rotate_threshold.value,
                       redo_ocr=redo_ocr.value, output_type="pdfa" if pdfa.value else "pdf",
                       extract_text=extract_text.value)
        start_job("ocr", "OCR", lambda job: run_ocr_batch(**options, on_progress=job.progress,
                                                          cancel=job.cancel_event),
                  output_dir=dst.value)

    run_button("Run OCR", start, "ocr")
    JobPanel("ocr", describe=lambda job: file_results(job, "processed"))
