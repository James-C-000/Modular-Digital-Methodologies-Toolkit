"""Co-word analysis page."""
import os
from nicegui import app, ui, run
from config import AppConfig


def cowords_page():
    config = AppConfig()

    ui.label("Co-Word Analysis").classes("text-h4")
    ui.label("Generate word co-occurrence networks to reveal conceptual relationships").classes("text-subtitle1")
    ui.separator()

    with ui.card().classes("w-full"):
        input_dir = ui.input("Input Directory").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_coword():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Downloading NLP data (if needed) and running co-word analysis...")

        try:
            def do_coword():
                from NLP.co_word_analysis import main as co_word_main
                co_word_main(in_dir)

            await run.io_bound(do_coword)
            status_label.set_text("Co-word analysis complete! Results saved in input directory.")
            ui.notify("Co-word analysis complete!", type="positive")

            summary = os.path.join(in_dir, "Co_Word_Analysis_Summary.html")
            if os.path.exists(summary):
                ui.label("Summary report generated.").classes("text-positive")
        except ImportError as e:
            status_label.set_text(f"Missing dependency: {e}")
            ui.notify(f"Missing dependency: {e}", type="negative")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Co-word analysis error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/cowords")
        config.save()

    ui.button("Run Analysis", on_click=run_coword, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.FOLDER,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
