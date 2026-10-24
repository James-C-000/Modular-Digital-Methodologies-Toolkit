"""Audio transcription page."""
import os

from nicegui import ui

from common.paths import folder_problem
from config import get_whisper_models_dir
from pages.components import (
    FolderField, JobPanel, file_results, hint, missing_dependency, page_header, remember, run_button, saved,
    section, start_job,
)

MODEL_NOTES = {
    "tiny": "Fastest, lowest accuracy. Good for quick drafts or testing.",
    "base": "Fast, more accurate than tiny. Suitable for clear audio.",
    "small": "Balanced speed and accuracy. Good for most recordings.",
    "medium": "Most accurate, slowest. Best for difficult audio or non-English speech.",
}


def audio_page():
    page_header("Audio Transcription", "Convert speech to text with Whisper (faster-whisper, runs offline)")
    try:
        from Audio_Transcription.transcription_logic import (
            DEFAULT_VAD, WHISPER_MODELS, is_model_installed, transcribe_directory,
        )
    except ImportError as e:
        missing_dependency(e)
        return

    models_root = get_whisper_models_dir()
    with section("Folder"):
        src = FolderField("Audio folder (searched recursively)", "defaults.audio_input_dir")
        hint("Each transcript is saved as a .txt file next to its recording.")

    with section("Model"):
        options = {n: f"{n} ({info['size']})" + ("" if is_model_installed(n, models_root) else " — downloads on first use")
                   for n, info in WHISPER_MODELS.items()}
        model = remember(ui.select(options, label="Whisper model",
                                   value=saved("defaults.whisper_model", "tiny")).classes("w-80"),
                         "defaults.whisper_model")
        note = hint("")
        model.on_value_change(lambda e: note.set_text(MODEL_NOTES.get(e.value, "")))
        note.set_text(MODEL_NOTES.get(model.value, ""))
        vad = remember(ui.checkbox("Skip silence (voice activity filter)",
                                   value=saved("defaults.whisper_vad", DEFAULT_VAD)), "defaults.whisper_vad")
        hint("Recommended for long recordings: skips silence, music and tape hiss, where Whisper tends to"
             " invent repeated phrases. Turn off if very quiet speech goes missing.")

    def describe(job):
        file_results(job, "transcribed")
        for r in job.result or []:
            if r.get("status") == "success" and r.get("text"):
                with ui.expansion(f"Transcript: {os.path.basename(r['input'])}").classes("w-full"):
                    text = r["text"]
                    ui.label(text[:2000] + ("..." if len(text) > 2000 else "")).classes("text-body2 whitespace-pre-wrap")

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        name, vad_on, folder = model.value, vad.value, src.value

        def work(job):
            job.progress(0, 0, f"Loading the {name} model...")
            return transcribe_directory(folder, model_name=name, download_root=models_root, vad_filter=vad_on,
                                        on_progress=job.progress, cancel=job.cancel_event)

        start_job("audio", "Transcription", work, output_dir=folder)

    run_button("Transcribe", start, "audio")
    JobPanel("audio", describe=describe)
