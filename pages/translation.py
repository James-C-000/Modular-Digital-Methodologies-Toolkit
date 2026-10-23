"""Translation page (offline, Argos Translate models)."""
import os

from nicegui import app, ui, run
from config import AppConfig

AUTO = "auto"


def translation_page():
    config = AppConfig()

    ui.label("Translation").classes("text-h4")
    ui.label("Translate documents offline with Argos Translate models").classes("text-subtitle1")
    ui.label(
        "Input PDFs must contain selectable text (be OCR'd). Scanned image-only PDFs"
        " cannot be translated — use the OCR module first to add a text layer."
    ).classes("text-caption text-grey")
    ui.separator()

    try:
        from Translation import offline_translation as ot
    except ImportError as e:
        ui.label(f"Missing dependency: {e}").classes("text-negative q-mt-md")
        ui.label("Install the required package via pip, then restart MDMT.")
        return

    names = ot.language_names()

    with ui.card().classes("w-full"):
        input_dir = ui.input("Input Directory", value=config.get("defaults.translation_input_dir", "")).classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center"):
            source_lang = ui.select(
                {AUTO: "Auto-detect", **names}, label="Translate from", with_input=True,
                value=config.get("defaults.translation_source", AUTO) if
                config.get("defaults.translation_source", AUTO) in {AUTO, *names} else AUTO,
            ).classes("w-64")
            target_lang = ui.select(
                names, label="Translate to", with_input=True,
                value=config.get("defaults.translation_target", "en") if
                config.get("defaults.translation_target", "en") in names else "en",
            ).classes("w-64")
        suffix = ui.input("Output Suffix", value=config.get("defaults.translation_suffix", ot.DEFAULT_SUFFIX)).classes("w-64")
        route_area = ui.column().classes("w-full")
        ui.label(
            "Offline translation keeps your documents on this computer. Quality is good for"
            " modern prose but can be weaker than online services for some language pairs,"
            " and historical terms are often mistranslated."
        ).classes("text-caption text-grey")

    progress_state = {"done": 0, "total": 0, "current": "", "busy": False}
    progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")
    results_area = ui.column().classes("w-full")

    def _size(src, tgt):
        info = ot.package_info(src, tgt)
        return f"{info['size'] / 1e6:.0f} MB" if info else "?"

    def needed_packages():
        """Packages required for the current choice that are not installed (or None if impossible)."""
        tgt = target_lang.value
        installed = ot.installed_pairs()
        if source_lang.value == AUTO:
            return [] if any(ot.route(s, tgt, available=installed) for s, _t in installed) else None
        src = source_lang.value
        best = ot.route(src, tgt, available=ot.index_pairs())
        if best is None:
            return None
        return [p for p in best if p not in installed]

    @ui.refreshable
    def show_route():
        tgt = target_lang.value
        if not tgt:
            return
        installed = ot.installed_pairs()
        if source_lang.value == AUTO:
            usable = sorted(s for s in {a for a, _b in installed} | {b for _a, b in installed}
                            if s != tgt and ot.route(s, tgt, available=installed))
            if usable:
                ui.label("Auto-detect will choose among: " + ", ".join(names.get(s, s) for s in usable)
                         ).classes("text-caption")
            else:
                ui.label(f"No installed model translates into {names[tgt]}. Choose the source"
                         " language to download the right model.").classes("text-caption text-warning")
            return
        src = source_lang.value
        if src == tgt:
            ui.label("Source and target are the same.").classes("text-caption text-warning")
            return
        steps = ot.route(src, tgt, available=ot.index_pairs())
        if steps is None:
            ui.label(f"No Argos model is available for {names[src]} → {names[tgt]}"
                     " (not even through English).").classes("text-caption text-negative")
            return
        if len(steps) > 1:
            ui.label(f"No direct {names[src]} → {names[tgt]} model: MDMT translates through"
                     " English, which compounds errors.").classes("text-caption text-warning")
        missing = [p for p in steps if p not in installed]
        if not missing:
            ui.label("Model(s) installed.").classes("text-caption text-positive")
            return
        with ui.row().classes("items-center"):
            ui.label("Needs: " + ", ".join(f"{names[a]} → {names[b]} ({_size(a, b)})" for a, b in missing)
                     ).classes("text-caption")
            ui.button("Download", icon="download", on_click=lambda: download_missing(missing)).props("flat dense")

    async def download_missing(pairs):
        for a, b in pairs:
            status_label.set_text(f"Downloading {names[a]} → {names[b]} ({_size(a, b)})...")
            try:
                await run.io_bound(ot.download_package, a, b)
            except Exception as e:
                status_label.set_text(f"Download failed: {e}")
                ui.notify(f"Download failed: {e}", type="negative")
                return
        status_label.set_text("Ready")
        show_route.refresh()

    with route_area:
        show_route()
    source_lang.on_value_change(lambda _e: show_route.refresh())
    target_lang.on_value_change(lambda _e: show_route.refresh())

    def _tick():
        if progress_state["busy"] and progress_state["total"]:
            progress.set_value(progress_state["done"] / progress_state["total"])
            status_label.set_text(
                f"Translating {progress_state['current']} ({progress_state['done']}/{progress_state['total']})...")

    ui.timer(0.3, _tick)

    async def run_translation():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return
        if needed_packages():
            ui.notify("Download the required model first (see above).", type="warning")
            return
        if needed_packages() is None:
            ui.notify("No model is available for this language pair.", type="warning")
            return

        src = None if source_lang.value == AUTO else source_lang.value
        tgt = target_lang.value
        sfx = suffix.value or ot.DEFAULT_SUFFIX
        results_area.clear()
        progress.set_visibility(True)
        progress_state.update(done=0, total=0, current="", busy=True)

        def on_progress(done, total, name):
            progress_state.update(done=done, total=total, current=name)

        try:
            results = await run.io_bound(ot.translate_directory, in_dir, src, tgt, sfx, None, on_progress)
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Translation error: {e}", type="negative")
            return
        finally:
            progress_state["busy"] = False
            progress.set_visibility(False)

        ok = sum(1 for r in results if r["status"] == "success")
        status_label.set_text(f"Complete: {ok}/{len(results)} files translated" if results
                              else "No .txt or .pdf files found.")
        with results_area:
            for r in results:
                good = r["status"] == "success"
                with ui.row().classes("items-center"):
                    ui.icon("check_circle" if good else "error").classes("text-positive" if good else "text-negative")
                    detail = os.path.basename(r["input"])
                    if r.get("language"):
                        detail += f" ({names.get(r['language'], r['language'])}" + (", via English)" if r.get("pivot") else ")")
                    if not good:
                        detail += f" — {r.get('message', r['status'])}"
                    ui.label(detail)

        config.set("defaults.translation_input_dir", in_dir)
        config.set("defaults.translation_source", source_lang.value)
        config.set("defaults.translation_target", tgt)
        config.set("defaults.translation_suffix", sfx)
        config.set("last_page", "/translation")
        config.save()

    ui.button("Translate", on_click=run_translation, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FileDialog.FOLDER,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
