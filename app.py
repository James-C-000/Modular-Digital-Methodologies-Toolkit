"""MDMT main application entry point with NiceGUI sidebar navigation."""
import multiprocessing

# Must come first.  In a frozen build every multiprocessing child (NiceGUI's
# native-window process, ocrmypdf workers) re-executes this program;
# freeze_support() hands such a child to its target and exits, so it never
# reaches the imports and setup below.
multiprocessing.freeze_support()

import common.launch  # noqa: F401  (records the std streams we were started with)
import os

# Jobs run in worker threads.  matplotlib's default macOS backend must not be
# used off the main thread, so force the non-interactive Agg backend before
# anything can import matplotlib.
os.environ["MPLBACKEND"] = "Agg"

import argparse
import logging
import sys

from nicegui import ui, app

from common.opener import open_external
from config import AppConfig, get_app_data_dir, get_nltk_data_dir
from version import __version__

log = logging.getLogger("mdmt")


# Open external links in the system browser instead of navigating within pywebview
@app.get('/api/open-external')
async def _open_external_url(url: str):
    if url.startswith(("http://", "https://")):
        open_external(url)
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
    """Configure environment for bundled assets when running as a frozen app."""
    if base_path is None:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    # --- Tesseract ---
    # Language data is handled by OCR.tessdata.configure_tessdata().
    tess_bin_dir = os.path.join(base_path, "tesseract_bin")
    if os.path.isdir(tess_bin_dir):
        os.environ["PATH"] = tess_bin_dir + os.pathsep + os.environ.get("PATH", "")
        if sys.platform == "linux":
            # Tesseract's bundled shared libs need to be discoverable via LD_LIBRARY_PATH
            os.environ["LD_LIBRARY_PATH"] = (
                tess_bin_dir + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
            )

    # --- SSL certificates ---
    # PyInstaller doesn't bundle system CA certs; point SSL at certifi's bundle.
    try:
        import certifi
        ca_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    except ImportError:
        pass


def _append_user_tool_paths():
    """Let a frozen macOS app find user-installed tools such as Ghostscript.

    Apps launched from Finder get a minimal PATH without Homebrew.  The
    directories are appended, so bundled tools always win.
    """
    if sys.platform != "darwin":
        return
    path = os.environ.get("PATH", "").split(os.pathsep)
    for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
        if extra not in path and os.path.isdir(extra):
            path.append(extra)
    os.environ["PATH"] = os.pathsep.join(p for p in path if p)


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


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="mdmt", description="Modular Digital Methodologies Toolkit")
    parser.add_argument("--self-test", action="store_true",
                        help="check the installation without opening a window, then exit")
    parser.add_argument("--self-test-out", metavar="PATH.json",
                        help="write the self-test report to this file")
    # parse_known_args: macOS may pass e.g. -psn_0_12345 to app bundles.
    args, _unknown = parser.parse_known_args(argv)
    return args


def main():
    """Initialize app data directory and start NiceGUI."""
    if multiprocessing.current_process().name != "MainProcess":
        # Defensive: a spawned child that somehow calls main() needs none of
        # the setup (see the __name__ guard at the bottom of this file).
        return

    args = _parse_args()

    from common.logs import setup_logging
    log_path = setup_logging()
    log.info("MDMT %s starting: pid=%d frozen=%s python=%s log=%s",
             __version__, os.getpid(), bool(getattr(sys, "frozen", False)),
             sys.version.split()[0], log_path)

    if getattr(sys, "frozen", False):
        _setup_frozen_env()
    _append_user_tool_paths()

    get_app_data_dir()

    from OCR.tessdata import configure_tessdata
    log.info("TESSDATA_PREFIX=%s", configure_tessdata())

    from common.downloads import remove_stale_parts
    from config import get_models_dir, get_tessdata_dir, get_whisper_models_dir
    for folder in (get_tessdata_dir(), get_whisper_models_dir(), get_models_dir()):
        remove_stale_parts(folder)

    # Point NLTK to our managed data directory
    import nltk
    nltk_dir = get_nltk_data_dir()
    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)

    if args.self_test:
        from selftest import run_self_test
        sys.exit(run_self_test(args.self_test_out))

    app.native.window_args["text_select"] = True
    ui.run(
        native=True,
        title=f"MDMT {__version__} - Modular Digital Methodologies Toolkit",
        window_size=(1200, 800),
        reload=False,
    )


# Only when run as a script.  Multiprocessing re-imports this module as
# "__mp_main__" in spawned children and in Python 3.14's forkserver process
# (which still calls itself "MainProcess"); neither must run main().  NiceGUI
# only needs "__mp_main__" here for reload mode, which MDMT does not use.
if __name__ == "__main__":
    main()
