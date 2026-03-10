"""MDMT main application entry point with NiceGUI sidebar navigation."""
import multiprocessing
try:
    multiprocessing.set_start_method('fork')
except RuntimeError:
    pass

import os
from nicegui import ui, app
from config import AppConfig, get_app_data_dir, get_nltk_data_dir


def create_sidebar():
    """Build the persistent sidebar navigation."""
    with ui.left_drawer(value=True).classes("bg-blue-grey-1") as drawer:
        ui.label("MDMT").classes("text-h5 q-mb-md")

        ui.label("Document Processing").classes("text-overline q-mt-md")
        ui.button("OCR", on_click=lambda: ui.navigate.to("/ocr"), icon="document_scanner").props("flat align=left").classes("w-full")
        ui.button("Audio Transcription", on_click=lambda: ui.navigate.to("/audio"), icon="mic").props("flat align=left").classes("w-full")
        ui.button("Translation", on_click=lambda: ui.navigate.to("/translation"), icon="translate").props("flat align=left").classes("w-full")

        ui.label("Analysis").classes("text-overline q-mt-lg")
        ui.button("Advanced Keywords", on_click=lambda: ui.navigate.to("/keywords"), icon="search").props("flat align=left").classes("w-full")
        ui.button("NER", on_click=lambda: ui.navigate.to("/ner"), icon="person_search").props("flat align=left").classes("w-full")
        ui.button("Relationships", on_click=lambda: ui.navigate.to("/relationships"), icon="hub").props("flat align=left").classes("w-full")
        ui.button("Co-Words", on_click=lambda: ui.navigate.to("/cowords"), icon="grain").props("flat align=left").classes("w-full")

        ui.label("AI").classes("text-overline q-mt-lg")
        ui.button("RAG Chat", on_click=lambda: ui.navigate.to("/rag"), icon="smart_toy").props("flat align=left").classes("w-full")

        ui.separator().classes("q-mt-lg")
        ui.button("Downloads", on_click=lambda: ui.navigate.to("/downloads"), icon="download").props("flat align=left").classes("w-full")
        ui.button("Help / About", on_click=lambda: ui.navigate.to("/about"), icon="info").props("flat align=left").classes("w-full")

    return drawer


@ui.page("/")
def index():
    config = AppConfig()
    if config.exists():
        last_page = config.get("last_page", "/welcome")
        ui.navigate.to(last_page)
    else:
        ui.navigate.to("/welcome")


@ui.page("/welcome")
def welcome():
    create_sidebar()
    from pages.welcome import welcome_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        welcome_page()


@ui.page("/about")
def about():
    create_sidebar()
    from pages.about import about_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        about_page()


@ui.page("/downloads")
def downloads():
    create_sidebar()
    from pages.downloads import downloads_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        downloads_page()


# Placeholder pages for modules not yet migrated
def _placeholder_page(name: str):
    def page_fn():
        create_sidebar()
        with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
            ui.label(f"{name}").classes("text-h4")
            ui.label("This module is not yet migrated to the web UI.").classes("text-subtitle1")
    return page_fn


for route, name in [
    ("/ocr", "OCR"),
    ("/audio", "Audio Transcription"),
    ("/translation", "Translation"),
    ("/keywords", "Advanced Keywords"),
    ("/ner", "NER"),
    ("/relationships", "Relationship Extraction"),
    ("/cowords", "Co-Word Analysis"),
    ("/rag", "RAG Chat"),
]:
    ui.page(route)(_placeholder_page(name))


def main():
    """Initialize app data directory and start NiceGUI."""
    get_app_data_dir()

    # Point NLTK to our managed data directory
    import nltk
    nltk_dir = get_nltk_data_dir()
    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)

    ui.run(
        native=True,
        title="MDMT - Modular Digital Methodologies Toolkit",
        window_size=(1200, 800),
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
