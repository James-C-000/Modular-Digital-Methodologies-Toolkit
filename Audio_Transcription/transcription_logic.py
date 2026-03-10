"""Audio transcription business logic extracted from audioTranscriptionWindow.py."""
import os

AUDIO_FORMATS = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")


def find_audio_files(directory: str) -> list[str]:
    """Walk a directory and return all audio file paths."""
    audio_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(AUDIO_FORMATS):
                audio_files.append(os.path.join(dirpath, filename))
    return audio_files


def transcribe_file(model, audio_path: str, output_path: str = None) -> dict:
    """Transcribe a single audio file using a loaded Whisper model.

    Args:
        model: A loaded whisper model instance.
        audio_path: Path to the audio file.
        output_path: Optional output .txt path. If None, uses audio_path + '.txt'.

    Returns:
        Dict with 'status', 'input', 'output', and optionally 'text' or 'message'.
    """
    if output_path is None:
        output_path = audio_path + ".txt"
    try:
        result = model.transcribe(audio_path)
        with open(output_path, "w") as f:
            f.write(result["text"])
        return {
            "status": "success",
            "input": audio_path,
            "output": output_path,
            "text": result["text"],
        }
    except Exception as e:
        return {"status": "error", "input": audio_path, "message": str(e)}


def transcribe_directory(
    directory: str,
    model_name: str = "tiny",
    download_root: str = None,
    on_progress=None,
) -> list[dict]:
    """Transcribe all audio files in a directory.

    Args:
        directory: Input directory to scan for audio files.
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium').
        download_root: Custom download directory for Whisper models.
        on_progress: Optional callback(current, total, filename).

    Returns:
        List of result dicts.
    """
    import whisper

    audio_files = find_audio_files(directory)
    if not audio_files:
        return []

    model = whisper.load_model(model_name, download_root=download_root)
    results = []

    for i, audio_path in enumerate(audio_files):
        if on_progress:
            on_progress(i, len(audio_files), os.path.basename(audio_path))

        result = transcribe_file(model, audio_path)
        results.append(result)

    if on_progress:
        on_progress(len(audio_files), len(audio_files), "Done")

    return results
