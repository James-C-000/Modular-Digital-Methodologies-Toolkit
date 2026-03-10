"""MDMT main application entry point with NiceGUI sidebar navigation."""
import multiprocessing
try:
    multiprocessing.set_start_method('fork')
except RuntimeError:
    pass

import os
import webbrowser
from nicegui import ui, app
from config import AppConfig, get_app_data_dir, get_nltk_data_dir


# Open external links in the system browser instead of navigating within pywebview
@app.get('/api/open-external')
async def _open_external_url(url: str):
    webbrowser.open(url)
    return {'ok': True}


ui.add_head_html('''<script>
document.addEventListener('click', function(e) {
    var link = e.target.closest('a');
    if (link && link.href &&
        (link.href.startsWith('http://') || link.href.startsWith('https://')) &&
        !link.href.startsWith(window.location.origin)) {
        e.preventDefault();
        e.stopPropagation();
        fetch('/api/open-external?url=' + encodeURIComponent(link.href));
    }
}, true);
</script>''', shared=True)


def create_sidebar():
    """Build the persistent sidebar navigation."""
    with ui.left_drawer(value=True).classes("bg-blue-grey-1") as drawer:
        ui.label("MDMT").classes("text-h5 q-mb-sm")

        ui.label("Document Processing").classes("text-overline q-mt-sm")
        ui.button("OCR", on_click=lambda: ui.navigate.to("/ocr"), icon="document_scanner").props("flat align=left").classes("w-full")
        ui.button("Audio Transcription", on_click=lambda: ui.navigate.to("/audio"), icon="mic").props("flat align=left").classes("w-full")
        ui.button("Translation", on_click=lambda: ui.navigate.to("/translation"), icon="translate").props("flat align=left").classes("w-full")

        ui.label("Analysis").classes("text-overline q-mt-sm")
        ui.button("Keyword Search", on_click=lambda: ui.navigate.to("/keywords"), icon="search").props("flat align=left").classes("w-full")
        ui.button("Named Entity Recognition", on_click=lambda: ui.navigate.to("/ner"), icon="person_search").props("flat align=left").classes("w-full")
        ui.button("Relationships", on_click=lambda: ui.navigate.to("/relationships"), icon="hub").props("flat align=left").classes("w-full")
        ui.button("Co-Words", on_click=lambda: ui.navigate.to("/cowords"), icon="grain").props("flat align=left").classes("w-full")

        ui.label("AI").classes("text-overline q-mt-sm")
        ui.button("RAGBot", on_click=lambda: ui.navigate.to("/rag"), icon="smart_toy").props("flat align=left").classes("w-full")

        ui.separator().classes("q-mt-sm")
        ui.button("Downloads", on_click=lambda: ui.navigate.to("/downloads"), icon="download").props("flat align=left").classes("w-full")
        ui.button("Help / About", on_click=lambda: ui.navigate.to("/about"), icon="info").props("flat align=left").classes("w-full")

    return drawer


@ui.page("/")
def index():
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


@ui.page("/ocr")
def ocr():
    create_sidebar()
    from pages.ocr import ocr_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ocr_page()


@ui.page("/audio")
def audio():
    create_sidebar()
    from pages.audio import audio_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        audio_page()


@ui.page("/translation")
def translation():
    create_sidebar()
    from pages.translation import translation_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        translation_page()


@ui.page("/keywords")
def keywords():
    create_sidebar()
    from pages.keywords import keywords_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        keywords_page()


@ui.page("/ner")
def ner():
    create_sidebar()
    from pages.ner import ner_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ner_page()


@ui.page("/relationships")
def relationships():
    create_sidebar()
    from pages.relationships import relationships_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        relationships_page()


@ui.page("/cowords")
def cowords():
    create_sidebar()
    from pages.cowords import cowords_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        cowords_page()


@ui.page("/rag")
def rag():
    create_sidebar()
    from pages.rag import rag_page
    with ui.column().classes("w-full h-full px-4 py-2").style("overflow: hidden"):
        rag_page()


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
