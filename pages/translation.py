"""Translation page (offline, Argos Translate models)."""
import os

from nicegui import ui

from common.jobs import JOBS
from common.paths import folder_problem
from pages.downloads import disclaimer, progress_text, start_downloads
from pages.components import (
    FolderField, JobPanel, file_results, hint, missing_dependency, page_header, remember, run_button, saved,
    section, start_job,
)

AUTO = "auto"


def translation_page():
    page_header("Translation", "Translate documents offline with Argos Translate models")
    try:
        from Translation import offline_translation as ot
    except ImportError as e:
        missing_dependency(e)
        return
    names = ot.language_names()

    with section("Folder"):
        src = FolderField("Input folder (.txt and .pdf, searched recursively)", "defaults.translation_input_dir")
        hint("PDFs must contain selectable text: run scanned PDFs through OCR first. Each translation is"
             " saved next to its original with the output suffix.")

    with section("Languages"):
        with ui.row().classes("items-center w-full"):
            saved_src = saved("defaults.translation_source", AUTO)
            source = remember(ui.select({AUTO: "Auto-detect", **names}, label="Translate from", with_input=True,
                                        value=saved_src if saved_src in {AUTO, *names} else AUTO).classes("w-64"),
                              "defaults.translation_source")
            saved_tgt = saved("defaults.translation_target", "en")
            target = remember(ui.select(names, label="Translate to", with_input=True,
                                        value=saved_tgt if saved_tgt in names else "en").classes("w-64"),
                              "defaults.translation_target")
            suffix = remember(ui.input("Output suffix", value=saved("defaults.translation_suffix", ot.DEFAULT_SUFFIX))
                              .classes("w-40"), "defaults.translation_suffix")
        route_area = ui.column().classes("w-full gap-1")
        hint("Offline translation keeps your documents on this computer. Quality is good for modern prose but"
             " can be weaker than online services for some language pairs.")
        disclaimer(ot.ARGOS_DISCLAIMER)

    def _size(a, b):
        info = ot.package_info(a, b)
        return f"{info['size'] / 1e6:.0f} MB" if info else "?"

    def needed_packages():
        """Packages the current choice needs that are not installed (None if no route exists)."""
        tgt = target.value
        installed = ot.installed_pairs()
        if source.value == AUTO:
            return [] if any(ot.route(s, tgt, available=installed) for s, _t in installed) else None
        best = ot.route(source.value, tgt, available=ot.index_pairs())
        return None if best is None else [p for p in best if p not in installed]

    @ui.refreshable
    def show_route():
        tgt = target.value
        if not tgt:
            return
        installed = ot.installed_pairs()
        if source.value == AUTO:
            usable = sorted(s for s in {a for a, _b in installed} | {b for _a, b in installed}
                            if s != tgt and ot.route(s, tgt, available=installed))
            if usable:
                hint("Auto-detect will choose among: " + ", ".join(names.get(s, s) for s in usable))
            else:
                ui.label(f"No installed model translates into {names[tgt]}. Choose the source language to"
                         " download the right model.").classes("text-caption text-warning")
            return
        src_lang = source.value
        if src_lang == tgt:
            ui.label("Source and target are the same.").classes("text-caption text-warning")
            return
        steps = ot.route(src_lang, tgt, available=ot.index_pairs())
        if steps is None:
            ui.label(f"No Argos model is available for {names[src_lang]} → {names[tgt]}"
                     " (not even through English).").classes("text-caption text-negative")
            return
        if len(steps) > 1:
            ui.label(f"No direct {names[src_lang]} → {names[tgt]} model: MDMT translates through English,"
                     " which compounds errors.").classes("text-caption text-warning")
        missing = [p for p in steps if p not in installed]
        if not missing:
            ui.label("Model(s) installed.").classes("text-caption text-positive")
            return
        downloading = JOBS.latest("translation-models")
        with ui.row().classes("items-center"):
            hint("Needs: " + ", ".join(f"{names[a]} → {names[b]} ({_size(a, b)})" for a, b in missing))
            if downloading and downloading.running:
                ui.spinner(size="xs")
                progress_label["label"] = hint(progress_text(downloading))
            else:
                ui.button("Download", icon="download", on_click=lambda: download(missing)).props("flat dense")

    progress_label = {"label": None}

    def download(pairs):
        from common.assets import find
        if start_downloads("translation-models", "Translation models",
                           [find(f"translation:{a}_{b}") for a, b in pairs]):
            show_route.refresh()

    # Refresh the route note when a model download (possibly started earlier) finishes.
    seen = {"status": None}

    def watch_downloads():
        job = JOBS.latest("translation-models")
        status = job and (job.id, job.status)
        if job and job.running and progress_label["label"] is not None:
            progress_label["label"].set_text(progress_text(job))
        if status != seen["status"]:
            seen["status"] = status
            if job and job.status == "failed":
                ui.notify(f"Download failed: {job.error}", type="negative")
            show_route.refresh()

    with route_area:
        show_route()
    ui.timer(0.5, watch_downloads)
    source.on_value_change(lambda _e: show_route.refresh())
    target.on_value_change(lambda _e: show_route.refresh())

    def describe(job):
        file_results(job, "translated")
        for r in job.result or []:
            if r.get("status") == "success" and r.get("language"):
                via = ", via English" if r.get("pivot") else ""
                hint(f"{os.path.basename(r['input'])}: {names.get(r['language'], r['language'])}{via}")

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        needed = needed_packages()
        if needed is None:
            return ui.notify("No model is available for this language pair.", type="warning")
        if needed:
            return ui.notify("Download the required model first (see above).", type="warning")
        folder, lang = src.value, None if source.value == AUTO else source.value
        tgt, sfx = target.value, suffix.value or ot.DEFAULT_SUFFIX
        start_job("translation", "Translation",
                  lambda job: ot.translate_directory(folder, lang, tgt, sfx, None, job.progress, job.cancel_event),
                  output_dir=folder)

    run_button("Translate", start, "translation")
    JobPanel("translation", describe=describe)
