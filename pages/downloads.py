"""Downloads page: every optional model and language file, from common.assets.

Downloads run as background jobs (kind "downloads-..."), so they continue
when the user leaves the page; rows show byte progress and update in place.
"""
import os

from nicegui import ui

from common.assets import Asset, human_bytes, recommended, section_bytes, sections
from common.jobs import JOBS
from pages.components import hint, page_header, section, start_job

PICKER_SECTIONS = {"ocr", "translation"}   # long lists: installed chips plus a searchable picker


def start_downloads(kind: str, title: str, items: list[Asset]):
    """Download *items* one after another in a background job (stops between items on cancel)."""
    items = [a for a in items if not a.installed()]
    if not items:
        ui.notify("Already installed.", type="info")
        return None

    def work(job):
        failures = []
        for i, asset in enumerate(items):
            if job.cancelled:
                break
            job.meta.update(asset=asset.key, step=i + 1, steps=len(items), name=asset.name)
            job.progress(0, asset.size or 0, asset.name)
            try:
                asset.download(lambda done, total: job.progress(done, total or 0, asset.name))
            except Exception as e:
                failures.append(f"{asset.name}: {e}")
        job.meta["asset"] = None
        if failures:
            raise RuntimeError("; ".join(failures))
        return len(items)

    return start_job(kind, title, work)


def downloading(asset_key: str):
    """The running download job fetching *asset_key*, if any."""
    return next((j for j in JOBS.running() if j.kind.startswith("downloads") and j.meta.get("asset") == asset_key),
                None)


def progress_text(job) -> str:
    step = f"{job.meta['step']} of {job.meta['steps']}: " if job.meta.get("steps", 1) > 1 else ""
    total = f" of {human_bytes(job.total)}" if job.total else ""
    return f"{step}{job.meta.get('name', '')} — {human_bytes(job.done)}{total}"


class ProgressLine:
    """A progress bar and caption that follow one download job."""

    def __init__(self, job):
        self.job = job
        with ui.column().classes("w-full gap-0"):
            self.bar = ui.linear_progress(value=0, show_value=False, size="6px").classes("w-full")
            with ui.row().classes("w-full items-center no-wrap"):
                self.text = hint("")
                ui.space()
                ui.button("Cancel", on_click=self.cancel).props("flat dense size=sm color=negative")
        self.update()

    def cancel(self):
        self.job.cancel()
        ui.notify("Stopping after the current download.", type="info")

    def update(self):
        if self.job.total:
            self.bar.props(remove="indeterminate")
            self.bar.set_value(self.job.done / self.job.total)
        else:
            self.bar.props("indeterminate")
        self.text.set_text(progress_text(self.job))


def disclaimer(text: str):
    with ui.row().classes("w-full items-start no-wrap gap-2 q-pa-sm rounded-borders mdmt-note"):
        ui.icon("info", size="xs").classes("q-mt-xs")
        ui.label(text).classes("text-caption")


def open_license(asset: Asset):
    from common.opener import open_external
    open_external(asset.license_path())


def confirm_delete(asset: Asset, on_done):
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete {asset.name}?").classes("text-subtitle1 text-weight-medium")
        hint(f"Frees {human_bytes(asset.disk_bytes())}. You can download it again later.")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def delete():
                dialog.close()
                try:
                    asset.delete()
                except RuntimeError as e:
                    ui.notify(str(e), type="warning", multi_line=True)
                on_done()

            ui.button("Delete", icon="delete", on_click=delete).props("color=negative unelevated")
    dialog.open()


def _section_view(sec_id: str, recommended_llm: str):
    """One section, rebuilt in place whenever a download in it starts or ends."""

    @ui.refreshable
    def body():
        sec = next(s for s in sections() if s.id == sec_id)
        with ui.row().classes("w-full items-baseline no-wrap"):
            ui.label(sec.title).classes("text-subtitle1 text-weight-medium")
            ui.space()
            hint(f"{human_bytes(section_bytes(sec))} on disk")
        if sec.note:
            hint(sec.note)
        if sec_id == "translation":
            from Translation.offline_translation import ARGOS_DISCLAIMER
            disclaimer(ARGOS_DISCLAIMER)
        hint(f"Location: {sec.location}")
        lines.clear()
        if sec_id in PICKER_SECTIONS:
            _picker_body(sec, body.refresh)
        else:
            for asset in sec.assets:
                _row(asset, body.refresh, star=asset.key == f"llm:{recommended_llm}")
        if sec_id == "whisper":
            _legacy_whisper(body.refresh)

    lines = []

    def _row(asset, refresh, star=False):
        installed = asset.installed()
        with ui.row().classes("w-full items-center no-wrap q-py-xs"):
            with ui.column().classes("gap-0 flex-grow"):
                label = asset.name + (f" ({human_bytes(asset.size)})" if asset.size else "")
                ui.label(label + ("  ★ Recommended for this computer" if star else "")).classes("text-body2")
                if asset.note:
                    hint(asset.note)
            job = downloading(asset.key)
            if installed:
                ui.label(f"Installed · {human_bytes(asset.disk_bytes())}").classes("text-positive text-body2 text-no-wrap")
                if not asset.bundled:
                    ui.button(icon="delete", on_click=lambda a=asset: confirm_delete(a, refresh)) \
                        .props("flat round dense").tooltip("Delete").mark(f"delete:{asset.key}")
            elif job is None:
                ui.button("Download", icon="download",
                          on_click=lambda a=asset: begin(f"downloads-{a.key}", a.name, [a])) \
                    .props("flat dense").mark(f"download:{asset.key}")
        if job is not None and not installed:
            lines.append(ProgressLine(job))

    def _picker_body(sec, refresh):
        installed = [a for a in sec.assets if a.installed()]
        ui.label(f"Installed ({len(installed)}):").classes("text-body2 q-mt-xs")
        with ui.row().classes("gap-1"):
            for a in installed:
                chip = ui.chip(a.name, removable=not a.bundled).props("outline dense color=positive")
                if a.bundled:
                    chip.tooltip("Ships with MDMT")
                else:
                    chip.on("remove", lambda _e, a=a: confirm_delete(a, refresh))
                if a.license_path():
                    chip.props("clickable").tooltip("Click to read this model's license (its README)")
                    chip.on_click(lambda a=a: open_license(a))
        job = JOBS.latest(f"downloads-{sec.id}")
        if job is not None and job.running:
            lines.append(ProgressLine(job))
            return
        options = {a.key: f"{a.name}" + (f" ({human_bytes(a.size)})" if a.size else "")
                   for a in sec.assets if not a.installed()}
        picker = ui.select(options, multiple=True, with_input=True,
                           label="Choose what to download (type to filter)").classes("w-full").props("use-chips")
        by_key = {a.key: a for a in sec.assets}
        ui.button("Download selected", icon="download",
                  on_click=lambda: begin(f"downloads-{sec.id}", sec.title,
                                         [by_key[k] for k in picker.value or []])).props("flat")

    def begin(kind, title, items):
        if not items:
            return ui.notify("Choose something to download first.", type="info")
        if start_downloads(kind, title, items):
            body.refresh()

    state = {"running": None}

    def tick():
        running = {(j.id, j.status) for j in JOBS.running() if j.kind.startswith("downloads")}
        if running != state["running"]:
            if state["running"] is not None:
                failed = [j for j in JOBS.all() if j.kind.startswith("downloads") and j.status == "failed"
                          and not j.meta.get("reported")]
                for j in failed:
                    j.meta["reported"] = True
                    ui.notify(f"Download failed: {j.error}", type="negative", multi_line=True)
            state["running"] = running
            body.refresh()
            return
        for line in lines:
            line.update()

    with section():
        body()
    ui.timer(0.5, tick)


def _legacy_whisper(refresh):
    from Audio_Transcription.transcription_logic import legacy_model_files
    from config import get_whisper_models_dir
    legacy = legacy_model_files(get_whisper_models_dir())
    if not legacy:
        return
    total = sum(os.path.getsize(p) for p in legacy)

    def delete():
        for p in legacy:
            try:
                os.remove(p)
            except OSError:
                pass
        refresh()

    with ui.row().classes("items-center w-full"):
        hint(f"{len(legacy)} old openai-whisper .pt file(s) ({human_bytes(total)}) are no longer used.")
        ui.button("Delete them", on_click=delete).props("flat dense")


def downloads_page():
    from RAG.hardware import detect_hardware
    page_header("Downloads", "Optional models and language data. Everything is downloaded from its official"
                             " source and runs offline afterwards.")
    hw = detect_hardware()
    hw_text = (f"{hw.gpu_type.upper()} GPU, {hw.vram_mb} MB VRAM" if hw.gpu_available
               else f"no GPU, {hw.ram_mb} MB RAM")
    with ui.row().classes("w-full items-center"):
        hint(f"This computer: {hw_text}.")
        ui.space()
        ui.button("Recommended setup", icon="auto_awesome", on_click=lambda: ui.navigate.to("/welcome")) \
            .props("flat dense")
    for sec in sections():
        _section_view(sec.id, hw.recommended_model)


def recommended_setup_card():
    """The Welcome page's one-click download of something for every tool."""
    from RAG.hardware import detect_hardware
    hw = detect_hardware()
    items = recommended(hw.recommended_model)

    @ui.refreshable
    def body():
        missing = [a for a in items if not a.installed()]
        ui.label("Recommended setup").classes("text-subtitle1 text-weight-medium")
        hint("One download for every tool: English OCR (included), a Whisper model, the named-entity model,"
             " the retrieval models and the chat model that suits this computer.")
        with ui.column().classes("w-full gap-0 q-my-sm"):
            for a in items:
                with ui.row().classes("items-center no-wrap gap-2"):
                    ok = a.installed()
                    ui.icon("check_circle" if ok else "radio_button_unchecked") \
                        .classes("text-positive" if ok else "mdmt-muted")
                    ui.label(f"{a.name}" + ("" if ok or a.size is None else f" ({human_bytes(a.size)})")) \
                        .classes("text-body2")
        job = JOBS.latest("downloads-recommended")
        lines.clear()
        if job is not None and job.running:
            lines.append(ProgressLine(job))
        elif missing:
            known = sum(a.size or 0 for a in missing)
            ui.button(f"Download all ({human_bytes(known)})", icon="download",
                      on_click=start).props("color=primary unelevated")
        else:
            ui.label("Everything recommended is installed.").classes("text-positive text-body2")
        if job is not None and job.status == "failed":
            ui.label(f"Some downloads failed: {job.error}").classes("text-negative text-body2")

    lines = []

    def start():
        if start_downloads("downloads-recommended", "Recommended setup", items):
            body.refresh()

    state = {"key": None}

    def tick():
        job = JOBS.latest("downloads-recommended")
        key = job and (job.id, job.status, job.meta.get("asset"))
        if key != state["key"]:
            state["key"] = key
            body.refresh()
            return
        for line in lines:
            line.update()

    with section():
        body()
    ui.timer(0.5, tick)
