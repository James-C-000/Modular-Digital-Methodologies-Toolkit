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

    # LLM Models
    with ui.card().classes("w-full mt-4"):
        ui.label("LLM Models (RAG Chat)").classes("text-h5")
        ui.label(f"Install location: {get_models_dir()}").classes("text-caption")

        models_dir = get_models_dir()
        gguf_files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")] if os.path.exists(models_dir) else []

        if gguf_files:
            for f in gguf_files:
                size_mb = os.path.getsize(os.path.join(models_dir, f)) / (1024 * 1024)
                ui.label(f"{f} ({size_mb:.0f} MB) - Installed").classes("text-positive")
        else:
            ui.markdown("""
No LLM models found. To add a model:

1. Download a GGUF model from [HuggingFace](https://huggingface.co)
2. Place it in the models directory shown above

Recommended: [`Llama-3.2-3B-Instruct-Q4_K_M.gguf`](https://huggingface.co/lmstudio-community/Llama-3.2-3B-Instruct-GGUF) (~2.0 GB)
            """)
