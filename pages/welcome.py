"""Welcome / first-run page."""
from nicegui import ui

from pages.components import page_header, section
from pages.downloads import recommended_setup_card


def welcome_page():
    page_header("Welcome to MDMT", "Modular Digital Methodologies Toolkit")

    with section("Getting started"):
        ui.markdown("""
MDMT brings together tools for digital humanities research, all running on
this computer:

- **Document processing**: OCR, audio transcription, translation
- **Text analysis**: keyword search, named entities, relationships, co-words
- **AI**: RAG Chat, which answers questions about your documents and cites its sources

Choose a tool in the sidebar. Jobs keep running while you look at other pages;
the sidebar shows what is running.
        """)

    recommended_setup_card()

    with section("Downloading only what you need"):
        ui.markdown("""
Every model and language file is optional, and you can add or remove each one
on the **Downloads** page:

- **OCR**: one file per language (1–15 MB each); English is included
- **Audio transcription**: Whisper models, 78 MB to 1.5 GB
- **Translation**: one model per language direction, 65–285 MB each
- **Named entities and relationships**: the multilingual NER model, 182 MB
- **RAG Chat**: retrieval models (135 MB, plus 588 MB for the optional reranker)
  and a Qwen 3.5 chat model (533 MB to 2.74 GB)
        """)
        ui.button("Open Downloads", icon="download", on_click=lambda: ui.navigate.to("/downloads")).props("outline")
