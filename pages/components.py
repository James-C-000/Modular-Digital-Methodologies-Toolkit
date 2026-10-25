"""Building blocks shared by the tool pages.

    page_header("OCR", "Add a text layer to scanned PDFs")
    src = FolderField("Input folder", "defaults.ocr_input_dir")
    remember(ui.checkbox("Deskew"), "defaults.ocr_deskew")
    panel = JobPanel("ocr", describe=file_results)
    run_button("Run OCR", start)          # disabled while an OCR job runs

Inputs remember their last value in the app config; jobs run in the app-level
job manager (common.jobs), and JobPanel re-attaches to the latest job of its
kind whenever the page is shown again.
"""
import os

from nicegui import ui

from common.jobs import JOBS, Busy
from config import AppConfig
from pages.pickers import pick_file, pick_folder

MAX_IMAGES = 12


# ---------------------------------------------------------- persistence ----

def saved(key: str, default=None):
    return AppConfig().get(key, default)


def save(key: str, value):
    config = AppConfig()
    config.set(key, value)
    config.save()


def remember(element, key: str):
    """Save *element*'s value under *key* whenever it changes; returns the element."""
    element.on_value_change(lambda e: save(key, e.value))
    return element


# ------------------------------------------------------------ structure ----

def page_header(title: str, subtitle: str | None = None):
    with ui.column().classes("w-full gap-0"):
        ui.label(title).classes("text-h5 text-weight-medium")
        if subtitle:
            ui.label(subtitle).classes("text-body2 mdmt-muted")
    ui.separator().classes("q-my-sm")


def section(title: str | None = None):
    """A card for one group of settings; use as a context manager."""
    card = ui.card().classes("w-full mdmt-section").props("flat bordered")
    if title:
        with card:
            ui.label(title).classes("text-subtitle1 text-weight-medium")
    return card


def hint(text: str):
    return ui.label(text).classes("text-caption mdmt-muted")


def missing_dependency(error: Exception):
    ui.label(f"Missing dependency: {error}").classes("text-negative q-mt-md")
    hint("Reinstall MDMT, or install the package with pip when running from source.")


def needs_download(title: str, text: str):
    with section():
        ui.label(title).classes("text-subtitle1 text-weight-medium")
        ui.label(text)
        ui.button("Go to Downloads", icon="download", on_click=lambda: ui.navigate.to("/downloads")) \
            .props("outline")


# --------------------------------------------------------------- pickers ----

class PathField:
    """A remembered, validated path input with a Browse button."""

    def __init__(self, label: str, key: str | None = None, kind: str = "folder", must_exist: bool = True,
                 extensions: list[str] | None = None, description: str = "Files"):
        self.kind, self.extensions, self.description = kind, extensions, description
        with ui.row().classes("w-full items-start no-wrap gap-1"):
            self.input = ui.input(label, value=saved(key, "") if key else "").classes("flex-grow")
            ui.button(icon="folder_open" if kind == "folder" else "description", on_click=self.browse) \
                .props("flat round").classes("q-mt-sm").tooltip("Browse...")
        if must_exist:
            exists = os.path.isdir if kind == "folder" else os.path.isfile
            message = "Folder not found." if kind == "folder" else "File not found."
            self.input.validation = {message: lambda v: not v or exists(os.path.expanduser(v.strip()))}
        if key:
            remember(self.input, key)

    @property
    def value(self) -> str:
        return os.path.expanduser((self.input.value or "").strip())

    def set_value(self, value: str):
        self.input.set_value(value)

    def error(self, message: str):
        """Show *message* under the field until it is edited."""
        self.input.props(f'error error-message="{message}"')
        self.input.on_value_change(lambda _e: self.input.props(remove="error error-message"))
        ui.notify(message, type="warning")

    async def browse(self):
        if self.kind == "folder":
            path = await pick_folder(self.value or None)
        else:
            path = await pick_file(self.value or None, self.extensions, self.description)
        if path:
            self.input.set_value(path)


def FolderField(label: str, key: str | None = None, must_exist: bool = True) -> PathField:  # noqa: N802
    return PathField(label, key, "folder", must_exist)


def FileField(label: str, key: str | None = None, extensions=None, description="Files") -> PathField:  # noqa: N802
    return PathField(label, key, "file", True, extensions, description)


# ------------------------------------------------------------------ jobs ----

def start_job(kind: str, title: str, work, output_dir: str | None = None):
    """Start a background job; returns it, or None (with a message) if one is already running."""
    try:
        return JOBS.start(kind, title, work, output_dir)
    except Busy as e:
        ui.notify(str(e), type="warning")
        return None


def run_button(label: str, on_click, kind: str, icon: str = "play_arrow"):
    """The page's main action; disabled while a job of *kind* runs."""
    button = ui.button(label, icon=icon, on_click=on_click).props("color=primary unelevated")
    ui.timer(0.5, lambda: button.set_enabled(not any(j.kind == kind for j in JOBS.running())))
    return button


def format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def open_folder(path: str):
    from common.opener import open_external
    if path and os.path.isdir(path):
        open_external(path)
    else:
        ui.notify("The folder no longer exists.", type="warning")


def file_results(job, ok_word: str = "done"):
    """Default result list for jobs whose result is a list of {"input", "status", "message"}."""
    results = job.result if isinstance(job.result, list) else []
    good = sum(1 for r in results if r.get("status") == "success")
    if not results:
        ui.label("No matching files were found in the folder.").classes("text-body2")
        return
    ui.label(f"{good} of {len(results)} file(s) {ok_word}.").classes("text-body2")
    with ui.column().classes("w-full gap-0"):
        for r in results:
            status = r.get("status")
            icon, color = {"success": ("check_circle", "text-positive"),
                           "skipped": ("remove_circle_outline", "mdmt-muted")}.get(status, ("error", "text-negative"))
            with ui.row().classes("items-center no-wrap gap-2"):
                ui.icon(icon).classes(color)
                text = os.path.basename(r.get("input", "?"))
                if status != "success" and r.get("message"):
                    text += f" — {r['message']}"
                ui.label(text).classes("text-body2")


def skipped_files(skipped, icon="remove_circle_outline", color="mdmt-muted"):
    """List the files a job could not use: [{"input": path, "message": why}].

    *icon* and *color* mark another kind of list, such as files used with a warning.
    """
    with ui.column().classes("w-full gap-0"):
        for r in skipped:
            with ui.row().classes("items-center no-wrap gap-2"):
                ui.icon(icon).classes(color)
                ui.label(f"{r['input']} — {r['message']}").classes("text-body2")


class JobPanel:
    """Progress, then results, of the latest job of *kind*.

    Built on every page visit; it attaches to whatever job is running or last
    finished, so leaving the page loses nothing.  *describe(job)* renders the
    page-specific result details.
    """

    def __init__(self, kind: str, describe=None):
        self.kind, self.describe = kind, describe
        self.container = ui.column().classes("w-full")
        self._shown = None
        self._bar = self._text = self._elapsed = self._cancel = None
        self._update()
        ui.timer(0.5, self._update)

    def _update(self):
        job = JOBS.latest(self.kind)
        key = (job.id, job.status) if job else None
        if key != self._shown:
            self._shown = key
            self.container.clear()
            if job is None:
                return
            with self.container:
                self._running_view(job) if job.running else self._finished_view(job)
        if job is not None and job.running:
            self._refresh_progress(job)

    def _running_view(self, job):
        with section():
            with ui.row().classes("w-full items-center no-wrap"):
                ui.spinner(size="sm")
                self._text = ui.label("").classes("text-body2 flex-grow ellipsis")
                self._elapsed = ui.label("").classes("text-caption mdmt-muted")
                self._cancel = ui.button("Cancel", icon="stop", on_click=lambda: self._request_cancel(job)) \
                    .props("flat dense color=negative")
            self._bar = ui.linear_progress(value=0, show_value=False).classes("w-full")

    def _request_cancel(self, job):
        job.cancel()
        self._cancel.disable()

    def _refresh_progress(self, job):
        if job.total:
            self._bar.props(remove="indeterminate")
            self._bar.set_value(job.done / job.total)
            text = f"{job.done} of {job.total} file(s)"
            if job.current:
                text += f" — {job.current}"
        else:
            self._bar.props("indeterminate")
            text = job.current or "Starting..."
        if job.cancelled:
            text = "Stopping after the current file..."
        self._text.set_text(text)
        self._elapsed.set_text(format_elapsed(job.elapsed))

    def _finished_view(self, job):
        with section():
            icon, color, text = {
                "done": ("check_circle", "text-positive", f"Finished in {format_elapsed(job.elapsed)}."),
                "cancelled": ("cancel", "text-warning",
                              f"Stopped after {job.done} of {job.total} file(s)." if job.total else "Stopped."),
                "failed": ("error", "text-negative", f"Failed: {job.error}"),
            }[job.status]
            with ui.row().classes("w-full items-center no-wrap"):
                ui.icon(icon, size="sm").classes(color)
                ui.label(text).classes("text-body1 flex-grow")
                if job.output_dir and job.status != "failed":
                    ui.button("Open output folder", icon="folder_open",
                              on_click=lambda: open_folder(job.output_dir)).props("flat dense")
            if job.summary:
                ui.label(job.summary).classes("text-body2")
            if self.describe is not None and job.status != "failed":
                self.describe(job)
            images = [p for p in job.images if os.path.isfile(p)]
            if images:
                image_grid(images)


def image_grid(paths: list[str]):
    """Thumbnails of generated images; click one to see it full size."""
    dialog = ui.dialog().props("maximized=false")
    with dialog, ui.card().classes("max-w-full"):
        big = ui.image().classes("w-[80vw] max-w-full")
        caption = ui.label("").classes("text-caption")
        ui.button("Close", on_click=dialog.close).props("flat")

    def show(path):
        big.set_source(path)
        big.force_reload()
        caption.set_text(os.path.basename(path))
        dialog.open()

    with ui.row().classes("w-full gap-2"):
        for path in paths[:MAX_IMAGES]:
            with ui.column().classes("gap-0 items-center cursor-pointer").on("click", lambda p=path: show(p)):
                img = ui.image(path).classes("w-40 h-28 rounded-borders mdmt-thumb").props("fit=contain")
                img.force_reload()
                ui.label(os.path.basename(path)).classes("text-caption ellipsis w-40 text-center")
    if len(paths) > MAX_IMAGES:
        hint(f"{len(paths) - MAX_IMAGES} more in the output folder.")
