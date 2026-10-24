"""Core audio transcription functions (faster-whisper on CTranslate2).

faster-whisper runs the OpenAI Whisper weights, converted to CTranslate2
format, and decodes audio in-process with PyAV, so no ffmpeg executable is
needed.  Inference runs on the CPU with int8 weights: CTranslate2 has no Metal
backend and MDMT does not bundle the CUDA libraries.

Models are downloaded on demand (Downloads page) into
``config.get_whisper_models_dir()/<name>/``.
"""
import os

AUDIO_FORMATS = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".flac", ".ogg")

# Systran's CTranslate2 conversions of the OpenAI Whisper checkpoints (MIT).
# Revisions are pinned so a model download is reproducible.
WHISPER_MODELS = {
    "tiny": {"repo_id": "Systran/faster-whisper-tiny",
             "revision": "d90ca5fe260221311c53c58e660288d3deb8d356", "size": "~78 MB"},
    "base": {"repo_id": "Systran/faster-whisper-base",
             "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66", "size": "~148 MB"},
    "small": {"repo_id": "Systran/faster-whisper-small",
              "revision": "536b0662742c02347bc0e980a01041f333bce120", "size": "~486 MB"},
    "medium": {"repo_id": "Systran/faster-whisper-medium",
               "revision": "08e178d48790749d25932bbc082711ddcfdfbc4f", "size": "~1.5 GB"},
}
_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")

# Voice-activity filter (Silero VAD, bundled with faster-whisper).  On by
# default: long archival recordings often contain silence, music or tape
# hiss, where Whisper tends to hallucinate repeated phrases; skipping
# non-speech also makes transcription faster.  A generous minimum silence
# keeps natural pauses inside a segment.  Users can switch it off for very
# quiet or noisy recordings where it might clip soft speech.
DEFAULT_VAD = True
VAD_PARAMETERS = {"min_silence_duration_ms": 2000, "speech_pad_ms": 400}


def model_dir(name: str, models_root: str) -> str:
    return os.path.join(models_root, name)


def is_model_installed(name: str, models_root: str) -> bool:
    from common.hf_models import is_snapshot_complete
    return is_snapshot_complete(model_dir(name, models_root), _MODEL_FILES)


def legacy_model_files(models_root: str) -> list[str]:
    """``.pt`` checkpoints left behind by the openai-whisper backend (v2.0.x)."""
    try:
        return sorted(
            os.path.join(models_root, f) for f in os.listdir(models_root) if f.endswith(".pt")
        )
    except OSError:
        return []


def download_model(name: str, models_root: str) -> str:
    """Download a Whisper model into ``models_root/<name>`` atomically."""
    from common.hf_models import download_snapshot
    info = WHISPER_MODELS[name]
    return download_snapshot(info["repo_id"], info["revision"], _MODEL_FILES, model_dir(name, models_root))


def load_model(name: str, models_root: str):
    """Load a faster-whisper model for CPU inference, downloading it if needed."""
    from faster_whisper import WhisperModel

    path = download_model(name, models_root)
    return WhisperModel(path, device="cpu", compute_type="int8")


def find_audio_files(directory: str) -> list[str]:
    """Walk a directory and return all audio file paths."""
    audio_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(AUDIO_FORMATS):
                audio_files.append(os.path.join(dirpath, filename))
    return sorted(audio_files)


def transcribe_file(model, audio_path: str, output_path: str = None, vad_filter: bool = DEFAULT_VAD) -> dict:
    """Transcribe a single audio file using a loaded faster-whisper model.

    Args:
        model: A loaded ``faster_whisper.WhisperModel``.
        audio_path: Path to the audio file.
        output_path: Optional output .txt path. If None, uses audio_path + '.txt'.
        vad_filter: Skip non-speech with the voice-activity filter.

    Returns:
        Dict with 'status', 'input', 'output', and optionally 'text' or 'message'.
    """
    if output_path is None:
        output_path = audio_path + ".txt"
    try:
        segments, info = model.transcribe(
            audio_path,
            vad_filter=vad_filter,
            vad_parameters=VAD_PARAMETERS if vad_filter else None,
        )
        # ``segments`` is a lazy generator: decoding happens while iterating.
        text = "".join(segment.text for segment in segments).strip()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        return {
            "status": "success",
            "input": audio_path,
            "output": output_path,
            "text": text,
            "language": info.language,
        }
    except Exception as e:
        return {"status": "error", "input": audio_path, "message": str(e)}


def transcribe_directory(
    directory: str,
    model_name: str = "tiny",
    download_root: str = None,
    on_progress=None,
    vad_filter: bool = DEFAULT_VAD,
    cancel=None,
) -> list[dict]:
    """Transcribe all audio files in a directory.

    Args:
        directory: Input directory to scan for audio files.
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium').
        download_root: Directory holding downloaded Whisper models.
        on_progress: Optional callback(current, total, filename).
        vad_filter: Skip non-speech with the voice-activity filter.
        cancel: Optional threading.Event; when set, stops before the next file.

    Returns:
        List of result dicts.
    """
    if download_root is None:
        from config import get_whisper_models_dir
        download_root = get_whisper_models_dir()

    audio_files = find_audio_files(directory)
    if not audio_files:
        return []

    model = load_model(model_name, download_root)
    results = []

    for i, audio_path in enumerate(audio_files):
        if cancel is not None and cancel.is_set():
            break
        if on_progress:
            on_progress(i, len(audio_files), os.path.basename(audio_path))

        result = transcribe_file(model, audio_path, vad_filter=vad_filter)
        results.append(result)

    if on_progress:
        on_progress(len(results), len(audio_files), "")

    return results
