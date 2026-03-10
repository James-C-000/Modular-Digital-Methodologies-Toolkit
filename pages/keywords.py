"""Advanced keyword search page."""
import os
from nicegui import app, ui, run
from config import AppConfig


def keywords_page():
    config = AppConfig()

    ui.label("Advanced Keyword Search").classes("text-h4")
    ui.label("Batch keyword analysis across PDF collections").classes("text-subtitle1")
    ui.separator()

    try:
        from Advanced_Keyword_Search.advancedKeywordSearchLogic import core_logic
    except ImportError as e:
        ui.label(f"Missing dependency: {e}").classes("text-negative q-mt-md")
        ui.label("Install the required package from the Downloads page or via pip, then restart MDMT.")
        return

    pdf_dir = ui.input("PDF Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(pdf_dir), icon="folder_open").props("flat")

    output_dir = ui.input("Output Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(output_dir), icon="folder_open").props("flat")

    context_length = ui.number("Context Length (words)", value=5, min=1, max=50).classes("w-48")

    ui.label("Keywords (one per line)").classes("text-subtitle2 q-mt-md")
    keywords_text = ui.textarea(placeholder="Enter keywords, one per line...").classes("w-full")

    with ui.row().classes("items-center"):
        basic_filter = ui.checkbox("Basic Filter (letters & numbers only)", value=False)
    filters_text = ui.textarea(placeholder="Enter filter words, one per line...").classes("w-full")

    with ui.expansion("Or load from files...").classes("w-full"):
        keyword_file = ui.input("Keyword File Path").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(keyword_file), icon="folder_open").props("flat")
        filter_file = ui.input("Filter File Path").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(filter_file), icon="folder_open").props("flat")

    ui.separator()

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_analysis():
        in_dir = pdf_dir.value
        out_dir = output_dir.value

        if not in_dir or not out_dir:
            ui.notify("Please select both input and output directories.", type="warning")
            return
        if in_dir == out_dir:
            ui.notify("Input and output directories cannot be the same.", type="warning")
            return

        manual_kw = keywords_text.value or ""
        manual_fl = filters_text.value or ""
        kw_file = keyword_file.value or ""
        fl_file = filter_file.value or ""

        if not manual_kw and not kw_file:
            ui.notify("Please enter keywords or select a keyword file.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Analyzing...")

        def do_analysis():
            core_logic(
                str(int(context_length.value)),
                1 if basic_filter.value else 0,
                in_dir,
                out_dir,
                kw_file,
                manual_kw,
                fl_file,
                manual_fl,
            )

        try:
            await run.io_bound(do_analysis)
            status_label.set_text("Analysis complete!")
            ui.notify("Keyword analysis complete! Check the output directory.", type="positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Analysis error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/keywords")
        config.save()

    ui.button("Analyze", on_click=run_analysis, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FOLDER_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])


async def _browse_file(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.OPEN_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
