"""Named Entity Recognition page."""
import os
from nicegui import app, ui, run
from config import AppConfig


def ner_page():
    config = AppConfig()

    ui.label("Named Entity Recognition").classes("text-h4")
    ui.label("Identify people, organizations, locations, and other entities in documents").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    ui.separator()

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_ner():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Loading NER model (may download ~1.3 GB on first run)...")

        try:
            def do_ner():
                from NLP.named_entity_recognition import main as ner_main
                ner_main(in_dir)

            await run.io_bound(do_ner)
            status_label.set_text("NER analysis complete! Results saved in input directory.")
            ui.notify("NER analysis complete!", type="positive")
        except ImportError as e:
            status_label.set_text(f"Missing dependency: {e}")
            ui.notify(f"Missing dependency: {e}", type="negative")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"NER error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/ner")
        config.save()

    ui.button("Run NER", on_click=run_ner, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.FOLDER,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
