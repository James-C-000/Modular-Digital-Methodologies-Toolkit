"""The single page that hosts every MDMT tool.

The sidebar is built once per window; tools are ``ui.sub_pages`` routes, so
moving between them swaps only the content area.  Work runs in the app-level
job manager (common.jobs), never in the content area, so leaving a tool while
it runs loses nothing; the sidebar lists running jobs.
"""
import importlib

from nicegui import app, context, ui

from common.jobs import JOBS
from common.ui_mode import use_native_window
from config import AppConfig

# path, label, icon, "module:function", job kind (if the tool runs jobs)
SECTIONS = [
    ("Document Processing", [
        ("/ocr", "OCR", "document_scanner", "pages.ocr:ocr_page"),
        ("/audio", "Audio Transcription", "mic", "pages.audio:audio_page"),
        ("/translation", "Translation", "translate", "pages.translation:translation_page"),
    ]),
    ("Analysis", [
        ("/keywords", "Keyword Search", "search", "pages.keywords:keywords_page"),
        ("/ner", "Named Entities", "person_search", "pages.ner:ner_page"),
        ("/relationships", "Relationships", "hub", "pages.relationships:relationships_page"),
        ("/cowords", "Co-Words", "grain", "pages.cowords:cowords_page"),
    ]),
    ("AI", [
        ("/rag", "RAGBot", "smart_toy", "pages.rag:rag_page"),
    ]),
    (None, [
        ("/downloads", "Downloads", "download", "pages.downloads:downloads_page"),
        ("/about", "Help / About", "info", "pages.about:about_page"),
    ]),
]
# A restrained desktop look: sentence-case buttons rather than Quasar's capitals.
ui.button.default_props("no-caps")

WELCOME = ("/welcome", "Welcome", "home", "pages.welcome:welcome_page")
ROUTES = [WELCOME] + [entry for _title, entries in SECTIONS for entry in entries]
FULL_HEIGHT = {"/rag"}  # pages that manage their own height (chat)

STYLE = """<style>
:root { --mdmt-muted: #616161; --mdmt-border: rgba(0,0,0,.12); --mdmt-drawer: #f3f3f3;
        --mdmt-bubble: #eceff1; --mdmt-bubble-text: #212121; --mdmt-active: rgba(25,118,210,.10); }
body.body--dark { --mdmt-muted: #a0a0a0; --mdmt-border: rgba(255,255,255,.14); --mdmt-drawer: #1b1b1b;
        --mdmt-bubble: #2b2f33; --mdmt-bubble-text: #e8e8e8; --mdmt-active: rgba(144,202,249,.16); }
.mdmt-muted { color: var(--mdmt-muted); }
.mdmt-drawer { background-color: var(--mdmt-drawer); }
.mdmt-section { border-color: var(--mdmt-border); }
.mdmt-thumb { border: 1px solid var(--mdmt-border); }
.mdmt-note { border: 1px solid var(--mdmt-border); background: var(--mdmt-active); }
.mdmt-nav .q-item { border-radius: 6px; min-height: 36px; padding: 4px 10px; }
.mdmt-nav .q-item.mdmt-active { background: var(--mdmt-active); color: var(--q-primary); font-weight: 500; }
.mdmt-nav .q-item__section--avatar { min-width: 34px; }
/* Assistant chat bubbles follow the theme (Quasar's default is a fixed green). */
.mdmt-chat .q-message-text--received { background: var(--mdmt-bubble); color: var(--mdmt-bubble-text); }
.mdmt-chat .q-message-text--received:last-child:before { border-bottom-color: var(--mdmt-bubble); }
.mdmt-chat .q-message-text-content--received { color: var(--mdmt-bubble-text); }
</style>"""


def _builder(target: str, path: str):
    module_name, function = target.split(":")

    def build():
        page = getattr(importlib.import_module(module_name), function)
        # The chat scrolls inside itself; every other page scrolls as a whole.
        if path in FULL_HEIGHT:
            ui.query(".q-page").style("overflow: hidden")
        else:
            ui.query(".q-page").style(remove="overflow: hidden")
        if path in FULL_HEIGHT:
            with ui.column().classes("w-full h-full px-4 py-2").style("overflow: hidden"):
                page()
        else:
            with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-3"):
                page()
    return build


def _nav_list():
    items = {}
    with ui.list().classes("w-full mdmt-nav").props("dense"):
        for title, entries in SECTIONS:
            if title:
                ui.item_label(title).props("header").classes("text-overline q-pt-sm q-pb-xs q-px-sm")
            else:
                ui.separator().classes("q-my-sm")
            for path, label, icon, _target in entries:
                with ui.item(on_click=lambda p=path: ui.navigate.to(p)).mark(f"nav:{path}") as item:
                    with ui.item_section().props("avatar"):
                        ui.icon(icon, size="xs")
                    ui.item_section(label)
                items[path] = item
    return items


def _jobs_list():
    labels = {path: label for path, label, _icon, _t in ROUTES}

    @ui.refreshable
    def jobs_view():
        running = JOBS.running()
        if not running:
            return
        ui.separator().classes("q-my-sm")
        ui.label("Running").classes("text-overline q-px-sm")
        for job in running:
            path = "/" + job.kind.split("-")[0]   # "rag-setup" belongs to /rag
            with ui.column().classes("w-full gap-0 q-px-sm q-py-xs cursor-pointer") \
                    .on("click", lambda p=path: ui.navigate.to(p)):
                ui.label(labels.get(path, job.title)).classes("text-body2")
                bar = ui.linear_progress(value=job.fraction or 0, show_value=False, size="4px")
                if job.fraction is None:
                    bar.props("indeterminate")
                bars.append((job, bar))

    bars = []
    jobs_view()

    def tick():
        if {j.id for j, _b in bars} != {j.id for j in JOBS.running()}:
            bars.clear()
            jobs_view.refresh()
            return
        for job, bar in bars:
            if job.fraction is not None:
                bar.props(remove="indeterminate")
                bar.set_value(job.fraction)

    ui.timer(1.0, tick)


def _sidebar():
    config = AppConfig()
    dark = ui.dark_mode(config.get("ui.dark_mode", False))
    with ui.left_drawer(value=True).classes("mdmt-drawer").props("width=230").style("padding: 8px"):
        with ui.row().classes("items-center q-px-sm q-pb-sm cursor-pointer") \
                .on("click", lambda: ui.navigate.to("/welcome")):
            ui.label("MDMT").classes("text-h5 text-weight-bold")
        items = _nav_list()
        _jobs_list()
        ui.space()
        ui.separator().classes("q-my-sm")

        def toggle_dark(e):
            dark.set_value(e.value)
            config.set("ui.dark_mode", e.value)
            config.save()

        ui.switch("Dark mode", value=config.get("ui.dark_mode", False), on_change=toggle_dark).props("dense")
        if not use_native_window():
            # In the browser, closing the tab does not stop the server.
            def quit_mdmt():
                running = JOBS.running()
                if running:
                    ui.notify(f"{len(running)} job(s) still running; cancel them first.", type="warning")
                    return
                ui.notify("MDMT has stopped. You can close this tab.", type="info", timeout=0)
                ui.timer(0.5, app.shutdown, once=True)

            ui.button("Quit MDMT", on_click=quit_mdmt, icon="power_settings_new") \
                .props("flat dense align=left no-caps").classes("w-full q-mt-xs")
    return items


def root():
    ui.add_head_html(STYLE)
    ui.query(".nicegui-content").classes("p-0")
    items = _sidebar()
    from common import bundle
    if bundle.PROBLEM:
        with ui.row().classes("w-full items-center no-wrap q-pa-sm bg-negative text-white"):
            ui.icon("error")
            ui.label(bundle.PROBLEM).classes("text-body2")

    def highlight(path: str):
        for item_path, item in items.items():
            if path.startswith(item_path):
                item.classes("mdmt-active")
            else:
                item.classes(remove="mdmt-active")

    routes = {path: _builder(target, path) for path, _label, _icon, target in ROUTES}
    routes["/"] = routes[WELCOME[0]]
    ui.sub_pages(routes).classes("w-full")
    context.client.sub_pages_router.on_path_changed(highlight)
    highlight(context.client.sub_pages_router.current_path)

