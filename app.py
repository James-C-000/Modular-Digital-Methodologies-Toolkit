"""MDMT main application entry point with NiceGUI sidebar navigation."""
import multiprocessing
import platform


def _preferred_start_method() -> str:
    """Return the preferred multiprocessing start method for the current OS."""
    if platform.system() == "Windows":
        return "spawn"
    return "fork"


try:
    multiprocessing.set_start_method(_preferred_start_method())
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


def _setup_frozen_env(base_path: str = None):
    """Configure environment for bundled Tesseract when running as a frozen app."""
    import sys
    if base_path is None:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    tess_bin_dir = os.path.join(base_path, "tesseract_bin")
    tessdata_dir = os.path.join(base_path, "tessdata")

    if os.path.isdir(tess_bin_dir):
        os.environ["PATH"] = tess_bin_dir + os.pathsep + os.environ.get("PATH", "")
    if os.path.isdir(tessdata_dir):
        os.environ["TESSDATA_PREFIX"] = tessdata_dir


def create_sidebar():
    """Build the persistent sidebar navigation."""
    config = AppConfig()
    dark = ui.dark_mode(config.get("ui.dark_mode", False))

    ui.add_head_html('''<style>
    body.body--light .mdmt-drawer { background-color: #eee; }
    body.body--dark .mdmt-drawer { background-color: #1a1a1a; }
    </style>''')
    with ui.left_drawer(value=True).classes("mdmt-drawer").style("padding: 8px") as drawer:
        ui.label("MDMT").classes("text-h4")

        ui.label("Document Processing").classes("text-overline")
        ui.button("OCR", on_click=lambda: ui.navigate.to("/ocr"), icon="document_scanner").props("flat dense align=left").classes("w-full")
        ui.button("Audio Transcription", on_click=lambda: ui.navigate.to("/audio"), icon="mic").props("flat dense align=left").classes("w-full")
        ui.button("Translation", on_click=lambda: ui.navigate.to("/translation"), icon="translate").props("flat dense align=left").classes("w-full")

        ui.label("Analysis").classes("text-overline")
        ui.button("Keyword Search", on_click=lambda: ui.navigate.to("/keywords"), icon="search").props("flat dense align=left").classes("w-full")
        ui.button("Named Entities", on_click=lambda: ui.navigate.to("/ner"), icon="person_search").props("flat dense align=left").classes("w-full")
        ui.button("Relationships", on_click=lambda: ui.navigate.to("/relationships"), icon="hub").props("flat dense align=left").classes("w-full")
        ui.button("Co-Words", on_click=lambda: ui.navigate.to("/cowords"), icon="grain").props("flat dense align=left").classes("w-full")

        ui.label("AI").classes("text-overline")
        ui.button("RAGBot", on_click=lambda: ui.navigate.to("/rag"), icon="smart_toy").props("flat dense align=left").classes("w-full")

        ui.separator()
        ui.button("Downloads", on_click=lambda: ui.navigate.to("/downloads"), icon="download").props("flat dense align=left").classes("w-full")
        ui.button("Help / About", on_click=lambda: ui.navigate.to("/about"), icon="info").props("flat dense align=left").classes("w-full")

        def toggle_dark(e):
            dark.set_value(e.value)
            config.set("ui.dark_mode", e.value)
            config.save()

        ui.switch("Dark Mode", value=config.get("ui.dark_mode", False), on_change=toggle_dark)

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
    import sys
    if getattr(sys, "frozen", False):
        _setup_frozen_env()

    get_app_data_dir()

    # Point NLTK to our managed data directory
    import nltk
    nltk_dir = get_nltk_data_dir()
    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)

    app.native.window_args["text_select"] = True
    ui.run(
        native=True,
        title="MDMT - Modular Digital Methodologies Toolkit",
        window_size=(1200, 800),
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
