"""Audio transcription page."""
import os
from nicegui import app, ui, run
from config import AppConfig, get_whisper_models_dir


def audio_page():
    config = AppConfig()

    ui.label("Audio Transcription").classes("text-h4")
    ui.label("Convert speech in audio files to text using Whisper (faster-whisper, runs offline)").classes("text-subtitle1")
    ui.separator()

    try:
        from Audio_Transcription.transcription_logic import (
            DEFAULT_VAD, WHISPER_MODELS, is_model_installed, transcribe_directory,
        )
    except ImportError as e:
        ui.label(f"Missing dependency: {e}").classes("text-negative q-mt-md")
        ui.label("Install the required package from the Downloads page or via pip, then restart MDMT.")
        return

    with ui.card().classes("w-full"):
        input_dir = ui.input("Audio Directory", value=config.get("defaults.audio_input_dir", "")).classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    with ui.card().classes("w-full"):
        models_root = get_whisper_models_dir()
        model_select = ui.select(
            {n: n + ("" if is_model_installed(n, models_root) else " (will download)") for n in WHISPER_MODELS},
            label="Whisper Model",
            value=config.get("defaults.whisper_model", "tiny"),
        ).classes("w-48")

        ui.markdown(
            f"**tiny** \u2014 Fastest, lowest accuracy. Good for quick drafts or testing. {WHISPER_MODELS['tiny']['size']}  \n"
            f"**base** \u2014 Fast with improved accuracy over tiny. Suitable for clear audio. {WHISPER_MODELS['base']['size']}  \n"
            f"**small** \u2014 Balanced speed and accuracy. Good for most use cases. {WHISPER_MODELS['small']['size']}  \n"
            f"**medium** \u2014 Best accuracy, slowest. Recommended for difficult audio or non-English. {WHISPER_MODELS['medium']['size']}  \n\n"
            "Larger models require more RAM and processing time but produce more accurate transcriptions."
        ).classes("text-caption text-grey")

        vad = ui.checkbox(
            "Skip silence (voice activity filter)",
            value=config.get("defaults.whisper_vad", DEFAULT_VAD),
        )
        ui.label(
            "Recommended for long recordings: skips silence, music and tape hiss, where Whisper"
            " tends to invent repeated phrases. Turn off if very quiet speech goes missing."
        ).classes("text-caption text-grey")

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
                download_root=models_root,
                vad_filter=vad.value,
            )

        try:
            results = await run.io_bound(do_transcribe)
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Transcription error: {e}", type="negative")
            return
        finally:
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
                    elif r["status"] == "error" and r.get("message"):
                        ui.label(r["message"]).classes("text-negative text-caption")

        config.set("defaults.whisper_model", model_select.value)
        config.set("defaults.whisper_vad", vad.value)
        config.set("defaults.audio_input_dir", audio_dir)
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
