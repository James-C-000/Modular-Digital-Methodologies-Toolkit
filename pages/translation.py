"""Translation page."""
import os
import asyncio
from nicegui import app, ui, run
from config import AppConfig
from Translation.googletranslateWrapper import LANGUAGE_CODES, translate_documents_async


def translation_page():
    config = AppConfig()

    ui.label("Translation").classes("text-h4")
    ui.label("Translate documents using Google Translate").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    target_lang = ui.select(
        list(LANGUAGE_CODES.keys()),
        label="Target Language",
        value=config.get("defaults.translation_target_lang_display", "Spanish"),
    ).classes("w-64")

    suffix = ui.input("Output Suffix", value="_translated").classes("w-64")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_translation():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        lang_code = LANGUAGE_CODES.get(target_lang.value, "en")
        progress.set_visibility(True)
        status_label.set_text(f"Translating to {target_lang.value}...")

        settings = {
            "TARGET_LANG": lang_code,
            "SUFFIX": suffix.value or "_translated",
            "DIRECTORY": in_dir,
            "MAX_CHARS": 5000,
        }

        def do_translate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(translate_documents_async(settings))
            loop.close()

        try:
            await run.io_bound(do_translate)
            status_label.set_text("Translation completed successfully!")
            ui.notify("Translation complete!", type="positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Translation error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("defaults.translation_target_lang_display", target_lang.value)
        config.set("last_page", "/translation")
        config.save()

    ui.button("Translate", on_click=run_translation, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FOLDER_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
