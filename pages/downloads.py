"""Asset manager / downloads page."""
import os
from nicegui import ui, run
from config import get_tessdata_dir, get_models_dir, get_whisper_models_dir, get_nltk_data_dir


# Known Tesseract language files available for download
TESSDATA_LANGUAGES = {
    "English": "eng",
    "French": "fra",
    "German": "deu",
    "Spanish": "spa",
    "Italian": "ita",
    "Portuguese": "por",
    "Russian": "rus",
    "Chinese Simplified": "chi_sim",
    "Chinese Traditional": "chi_tra",
    "Japanese": "jpn",
    "Korean": "kor",
    "Arabic": "ara",
    "Hindi": "hin",
    "Dutch": "nld",
    "Swedish": "swe",
}

TESSDATA_GITHUB_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"

WHISPER_MODELS = {
    "tiny": "~75 MB",
    "base": "~142 MB",
    "small": "~466 MB",
    "medium": "~1.5 GB",
}


def _is_tessdata_installed(lang_code: str) -> bool:
    return os.path.exists(os.path.join(get_tessdata_dir(), f"{lang_code}.traineddata"))


def _is_whisper_installed(model_name: str) -> bool:
    model_dir = get_whisper_models_dir()
    return os.path.exists(os.path.join(model_dir, f"{model_name}.pt"))


async def _download_tessdata(lang_code: str, status_label: ui.label):
    """Download a single Tesseract language file."""
    import urllib.request

    url = f"{TESSDATA_GITHUB_URL}/{lang_code}.traineddata"
    dest = os.path.join(get_tessdata_dir(), f"{lang_code}.traineddata")
    status_label.set_text(f"Downloading {lang_code}...")

    def do_download():
        urllib.request.urlretrieve(url, dest)

    await run.io_bound(do_download)
    status_label.set_text(f"{lang_code} installed")


async def _download_whisper_model(model_name: str, status_label: ui.label):
    """Download a Whisper model via the whisper library."""
    status_label.set_text(f"Downloading {model_name}...")

    def do_download():
        import whisper
        whisper.load_model(model_name, download_root=get_whisper_models_dir())

    await run.io_bound(do_download)
    status_label.set_text(f"{model_name} installed")


async def _download_qwen_model(model: dict, status_label: ui.label):
    """Download a Qwen GGUF model from HuggingFace."""
    from huggingface_hub import hf_hub_download

    status_label.set_text(f"Downloading {model['name']}...")
    status_label.classes("text-warning", remove="text-grey")

    def do_download():
        hf_hub_download(
            repo_id=model["repo_id"],
            filename=model["filename"],
            local_dir=get_models_dir(),
        )

    try:
        await run.io_bound(do_download)
        status_label.set_text("Installed")
        status_label.classes("text-positive", remove="text-warning")
    except Exception as e:
        status_label.set_text(f"Download failed: {e}")
        status_label.classes("text-negative", remove="text-warning")
        # Clean up partial download if it exists
        partial_path = os.path.join(get_models_dir(), model["filename"])
        if os.path.exists(partial_path):
            try:
                os.remove(partial_path)
            except OSError:
                pass


def downloads_page():
    ui.label("Downloads & Models").classes("text-h4")
    ui.label("Manage optional assets. Downloads come from official sources.").classes("text-subtitle1")
    ui.separator()

    # Tesseract Languages
    with ui.card().classes("w-full"):
        ui.label("OCR Languages (Tesseract)").classes("text-h5")
        ui.label(f"Install location: {get_tessdata_dir()}").classes("text-caption")

        for display_name, lang_code in TESSDATA_LANGUAGES.items():
            installed = _is_tessdata_installed(lang_code)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{display_name} ({lang_code})").classes("w-48")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )
                if not installed:
                    ui.button(
                        "Download",
                        on_click=lambda lc=lang_code, sl=status: _download_tessdata(lc, sl),
                    ).props("flat dense")

    # Whisper Models
    with ui.card().classes("w-full mt-4"):
        ui.label("Whisper Models (Audio Transcription)").classes("text-h5")
        ui.label(f"Install location: {get_whisper_models_dir()}").classes("text-caption")

        for model_name, size in WHISPER_MODELS.items():
            installed = _is_whisper_installed(model_name)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{model_name} ({size})").classes("w-48")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )
                if not installed:
                    ui.button(
                        "Download",
                        on_click=lambda mn=model_name, sl=status: _download_whisper_model(mn, sl),
                    ).props("flat dense")

    # NLTK Data
    with ui.card().classes("w-full mt-4"):
        ui.label("NLTK Data (NER, Co-Word Analysis)").classes("text-h5")
        ui.label(f"Install location: {get_nltk_data_dir()}").classes("text-caption")

        nltk_packages = {
            "punkt_tab": "Sentence tokenizer",
            "averaged_perceptron_tagger_eng": "POS tagger",
            "maxent_ne_chunker_tab": "Named entity chunker",
            "words": "English word list",
            "stopwords": "Stop words",
        }

        for pkg_name, description in nltk_packages.items():
            pkg_dir = os.path.join(get_nltk_data_dir(), "tokenizers" if "punkt" in pkg_name else "taggers" if "tagger" in pkg_name else "chunkers" if "chunker" in pkg_name else "corpora", pkg_name)
            installed = os.path.exists(pkg_dir)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{description} ({pkg_name})").classes("w-64")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )

        async def download_all_nltk(status_label):
            status_label.set_text("Downloading NLTK data...")

            def do_download():
                import nltk
                nltk_dir = get_nltk_data_dir()
                for pkg in nltk_packages:
                    nltk.download(pkg, download_dir=nltk_dir, quiet=True)

            await run.io_bound(do_download)
            status_label.set_text("All NLTK data installed")

        nltk_status = ui.label("")
        ui.button("Download All NLTK Data", on_click=lambda: download_all_nltk(nltk_status)).props("flat")

    # LLM Models (Qwen 3.5)
    with ui.card().classes("w-full mt-4"):
        ui.label("LLM Models (RAG Chat)").classes("text-h5")
        ui.label(f"Install location: {get_models_dir()}").classes("text-caption")

        from RAG.hardware import detect_hardware
        hw_info = detect_hardware()

        hw_text = f"{hw_info.gpu_type.upper()} GPU — {hw_info.vram_mb} MB VRAM" if hw_info.gpu_available else f"No GPU — {hw_info.ram_mb} MB RAM"
        ui.label(f"Detected: {hw_text}").classes("text-caption")

        qwen_models = [
            {
                "name": "Qwen3.5-0.8B-Q4_K_M",
                "filename": "Qwen3.5-0.8B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-0.8B-GGUF",
                "size": "~533 MB",
                "desc": "Best for systems with < 2 GB available",
                "key": "0.8B",
            },
            {
                "name": "Qwen3.5-2B-Q4_K_M",
                "filename": "Qwen3.5-2B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-2B-GGUF",
                "size": "~1.28 GB",
                "desc": "Good balance for 2–4 GB systems",
                "key": "2B",
            },
            {
                "name": "Qwen3.5-4B-Q4_K_M",
                "filename": "Qwen3.5-4B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-4B-GGUF",
                "size": "~2.74 GB",
                "desc": "Best quality, requires 4+ GB",
                "key": "4B",
            },
        ]

        models_dir = get_models_dir()

        for model in qwen_models:
            model_path = os.path.join(models_dir, model["filename"])
            installed = os.path.exists(model_path)
            is_recommended = model["key"] == hw_info.recommended_model

            with ui.row().classes("items-center w-full"):
                label_text = f"{model['name']} ({model['size']})"
                if is_recommended:
                    label_text += " ★ Recommended"
                ui.label(label_text).classes("w-80")

                if installed:
                    size_mb = os.path.getsize(model_path) / (1024 * 1024)
                    ui.label(f"Installed ({size_mb:.0f} MB)").classes("text-positive")
                else:
                    status = ui.label("Not installed").classes("text-grey")
                    ui.button(
                        "Download",
                        on_click=lambda m=model, sl=status: _download_qwen_model(m, sl),
                    ).props("flat dense")

            ui.label(model["desc"]).classes("text-caption ml-2")
