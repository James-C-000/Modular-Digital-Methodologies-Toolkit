"""Audio transcription page."""
import os
from nicegui import app, ui, run
from config import AppConfig, get_whisper_models_dir


def audio_page():
    config = AppConfig()

    ui.label("Audio Transcription").classes("text-h4")
    ui.label("Convert speech in audio files to text using OpenAI Whisper").classes("text-subtitle1")
    ui.separator()

    try:
        from Audio_Transcription.transcription_logic import transcribe_directory
    except ImportError as e:
        ui.label(f"Missing dependency: {e}").classes("text-negative q-mt-md")
        ui.label("Install the required package from the Downloads page or via pip, then restart MDMT.")
        return

    input_dir = ui.input("Audio Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    model_select = ui.select(
        ["tiny", "base", "small", "medium"],
        label="Whisper Model",
        value=config.get("defaults.whisper_model", "tiny"),
    ).classes("w-48")

    ui.separator()

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")
    results_area = ui.column().classes("w-full")

    async def run_transcription():
        audio_dir = input_dir.value
        if not audio_dir:
            ui.notify("Please select an audio directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Loading model and transcribing...")
        results_area.clear()

        def do_transcribe():
            return transcribe_directory(
                directory=audio_dir,
                model_name=model_select.value,
                download_root=get_whisper_models_dir(),
            )

        results = await run.io_bound(do_transcribe)
        progress.set_visibility(False)

        if not results:
            status_label.set_text("No audio files found in the selected directory.")
            return

        success_count = sum(1 for r in results if r["status"] == "success")
        status_label.set_text(f"Complete: {success_count}/{len(results)} files transcribed")

        with results_area:
            for r in results:
                with ui.card().classes("w-full"):
                    icon = "check_circle" if r["status"] == "success" else "error"
                    color = "text-positive" if r["status"] == "success" else "text-negative"
                    with ui.row().classes("items-center"):
                        ui.icon(icon).classes(color)
                        ui.label(os.path.basename(r["input"]))
                    if r["status"] == "success" and r.get("text"):
                        preview = r["text"][:500] + ("..." if len(r["text"]) > 500 else "")
                        with ui.expansion("Preview transcript"):
                            ui.label(preview).classes("font-mono text-sm")

        config.set("defaults.whisper_model", model_select.value)
        config.set("last_page", "/audio")
        config.save()

    ui.button("Transcribe", on_click=run_transcription, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.FOLDER,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
