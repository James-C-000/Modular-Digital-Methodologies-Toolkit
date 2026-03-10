"""OCR processing page."""
import os
from nicegui import app, ui, run
from config import AppConfig, get_tessdata_dir
from OCR.ocr_logic import TESSERACT_LANGUAGES, run_ocr_batch


def _find_tessdata_dir() -> str:
    app_tessdata = get_tessdata_dir()
    bundled_tessdata = os.path.join(os.path.dirname(os.path.dirname(__file__)), "OCR", "tessdata")
    if os.path.isdir(app_tessdata) and any(f.endswith(".traineddata") for f in os.listdir(app_tessdata)):
        return app_tessdata
    if os.path.isdir(bundled_tessdata):
        return bundled_tessdata
    return app_tessdata


def ocr_page():
    config = AppConfig()
    tessdata_dir = _find_tessdata_dir()

    available_langs = {
        name: code for name, code in TESSERACT_LANGUAGES.items()
        if os.path.exists(os.path.join(tessdata_dir, f"{code}.traineddata"))
    }

    if not available_langs:
        with ui.card().classes("w-full"):
            ui.label("No OCR languages installed").classes("text-h5 text-negative")
            ui.label("Please download at least one language from the Downloads page.")
            ui.button("Go to Downloads", on_click=lambda: ui.navigate.to("/downloads")).props("outline")
        return

    ui.label("OCR Processing").classes("text-h4")
    ui.separator()

    input_dir = ui.input("Input Directory", value=config.get("defaults.ocr_input_dir", "")).classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    output_dir = ui.input("Output Directory", value=config.get("defaults.ocr_output_dir", "")).classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(output_dir), icon="folder_open").props("flat")

    lang_select = ui.select(
        list(available_langs.keys()),
        multiple=True,
        label="Languages",
        value=["English"] if "English" in available_langs else [],
    ).classes("w-full")

    with ui.row().classes("w-full"):
        deskew = ui.checkbox("Deskew", value=False)
        rotate = ui.checkbox("Rotate Pages", value=False)
        redo_ocr = ui.checkbox("Redo OCR", value=False)
        pdfa = ui.checkbox("PDF/A Output", value=False)
        extract_text = ui.checkbox("Extract Text", value=False)

    with ui.row().classes("w-full").bind_visibility_from(rotate, "value"):
        ui.label("Rotation Confidence:")
        rotate_threshold = ui.radio({2: "Low", 15: "Normal", 30: "High"}, value=15).props("inline")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")
    results_table = ui.column().classes("w-full")

    async def run_ocr():
        in_dir = input_dir.value
        out_dir = output_dir.value

        if not in_dir or not out_dir:
            ui.notify("Please select both input and output directories.", type="warning")
            return
        if in_dir == out_dir:
            ui.notify("Input and output directories cannot be the same.", type="warning")
            return
        if not lang_select.value:
            ui.notify("Please select at least one language.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Processing...")
        results_table.clear()

        def do_ocr():
            return run_ocr_batch(
                input_dir=in_dir,
                output_dir=out_dir,
                tessdata_dir=tessdata_dir,
                language_names=lang_select.value,
                deskew=deskew.value,
                rotate_pages=rotate.value,
                rotate_threshold=rotate_threshold.value,
                redo_ocr=redo_ocr.value,
                output_type="pdfa" if pdfa.value else "pdf",
                extract_text=extract_text.value,
            )

        results = await run.io_bound(do_ocr)
        progress.set_visibility(False)

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        status_label.set_text(f"Complete: {success_count} succeeded, {error_count} failed")

        with results_table:
            for r in results:
                icon = "check_circle" if r["status"] == "success" else "error"
                color = "text-positive" if r["status"] == "success" else "text-negative"
                msg = os.path.basename(r["input"])
                if r["status"] == "error":
                    msg += f" — {r.get('message', 'Unknown error')}"
                with ui.row().classes("items-center"):
                    ui.icon(icon).classes(color)
                    ui.label(msg)

        config.set("defaults.ocr_input_dir", in_dir)
        config.set("defaults.ocr_output_dir", out_dir)
        config.set("last_page", "/ocr")
        config.save()

    ui.button("Run OCR", on_click=run_ocr, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FOLDER_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
