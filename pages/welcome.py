"""Welcome / first-run page."""
from nicegui import ui
from config import AppConfig


def welcome_page():
    config = AppConfig()

    ui.label("Welcome to MDMT").classes("text-h3")
    ui.label("Modular Digital Methodologies Toolkit").classes("text-subtitle1")

    ui.separator()

    with ui.card().classes("w-full"):
        ui.label("Getting Started").classes("text-h5")
        ui.markdown("""
MDMT provides tools for digital humanities research:

- **Document Processing** — OCR, Audio Transcription, Translation
- **Text Analysis** — Keyword Search, Named Entity Recognition, Relationship Extraction, Co-Word Analysis
- **AI** — RAG Chatbot for querying your documents

Use the sidebar to navigate to any module. Some modules require downloading
models or language data first — visit the **Downloads** page to manage these.
        """)

    with ui.card().classes("w-full mt-4"):
        ui.label("Optional Downloads").classes("text-h5")
        ui.markdown("""
Some features require additional data to be downloaded:

- **OCR**: Tesseract language files (~12-15 MB each)
- **Audio Transcription**: Whisper models (75 MB - 1.5 GB)
- **RAG Chat**: Llama LLM model (~2.3 GB)

You can download these from the **Downloads** page, or they will prompt you when needed.
        """)
        ui.button("Go to Downloads", on_click=lambda: ui.navigate.to("/downloads")).props("outline")
