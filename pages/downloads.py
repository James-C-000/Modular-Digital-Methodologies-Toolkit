"""Asset manager / downloads page."""
import os
from nicegui import ui, run
from config import get_tessdata_dir, get_models_dir, get_whisper_models_dir


TESSDATA_GITHUB_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"


def _human_bytes(n) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _tessdata_section():
    from OCR.ocr_logic import downloadable_tessdata
    from OCR.tessdata import installed_languages
    from common.downloads import download_file

    tessdata_dir = get_tessdata_dir()
    registry = downloadable_tessdata()
    names_by_code = {code: name for name, code in registry.items()}

    with ui.card().classes("w-full"):
        ui.label("OCR Languages (Tesseract)").classes("text-h5")
        ui.label(f"Install location: {tessdata_dir}").classes("text-caption")

        @ui.refreshable
        def installed_view():
            installed = sorted(installed_languages(tessdata_dir))
            ui.label(f"Installed ({len(installed)}):").classes("text-subtitle2")
            with ui.row().classes("gap-1"):
                for code in installed:
                    ui.chip(f"{names_by_code.get(code, code)} ({code})", color="positive").props("outline dense")

        installed_view()

        def not_installed_options():
            have = installed_languages(tessdata_dir)
            return {code: f"{name} ({code})" for name, code in sorted(registry.items()) if code not in have}

        picker = ui.select(
            not_installed_options(), multiple=True, with_input=True,
            label="Choose languages to download (type to filter)",
        ).classes("w-full").props("use-chips")
        state = {"done": 0, "total": None, "current": "", "busy": False}
        progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
        progress.set_visibility(False)
        status = ui.label("").classes("text-caption")

        def _tick():
            if state["busy"]:
                frac = state["done"] / state["total"] if state["total"] else 0
                progress.set_value(frac)
                status.set_text(
                    f"Downloading {state['current']}: {_human_bytes(state['done'])}"
                    f" of {_human_bytes(state['total'])}"
                )

        ui.timer(0.25, _tick)

        async def download_selected():
            codes = list(picker.value or [])
            if not codes or state["busy"]:
                return
            state["busy"] = True
            progress.set_visibility(True)
            failures = []
            for code in codes:
                state.update(done=0, total=None, current=code)
                dest = os.path.join(tessdata_dir, f"{code}.traineddata")
                try:
                    await run.io_bound(
                        download_file, f"{TESSDATA_GITHUB_URL}/{code}.traineddata", dest,
                        lambda d, t: state.update(done=d, total=t),
                    )
                except Exception as e:
                    failures.append(f"{code}: {e}")
            state["busy"] = False
            progress.set_visibility(False)
            picker.set_options(not_installed_options(), value=[])
            installed_view.refresh()
            if failures:
                status.set_text("Failed — " + "; ".join(failures))
                status.classes("text-negative", remove="text-positive")
                ui.notify("Some downloads failed: " + "; ".join(failures), type="negative", multi_line=True)
            else:
                status.set_text(f"Installed {', '.join(codes)}")
                status.classes("text-positive", remove="text-negative")

        ui.button("Download selected", icon="download", on_click=download_selected).props("flat")


def _whisper_section():
    from Audio_Transcription.transcription_logic import (
        WHISPER_MODELS, download_model, is_model_installed, legacy_model_files,
    )

    models_root = get_whisper_models_dir()
    with ui.card().classes("w-full mt-4"):
        ui.label("Whisper Models (Audio Transcription)").classes("text-h5")
        ui.label(f"Install location: {models_root}").classes("text-caption")
        ui.label(
            "CTranslate2 conversions of OpenAI Whisper (MIT), run with faster-whisper."
        ).classes("text-caption text-grey")

        @ui.refreshable
        def rows():
            for name, info in WHISPER_MODELS.items():
                installed = is_model_installed(name, models_root)
                with ui.row().classes("items-center w-full"):
                    ui.label(f"{name} ({info['size']})").classes("w-48")
                    status = ui.label("Installed" if installed else "Not installed").classes(
                        "text-positive" if installed else "text-grey"
                    )
                    if not installed:
                        ui.button(
                            "Download", on_click=lambda n=name, sl=status: download(n, sl),
                        ).props("flat dense")

            legacy = legacy_model_files(models_root)
            if legacy:
                total = sum(os.path.getsize(p) for p in legacy)
                with ui.row().classes("items-center w-full"):
                    ui.label(
                        f"{len(legacy)} old openai-whisper .pt file(s) ({_human_bytes(total)}) are no longer used."
                    ).classes("text-caption")
                    ui.button("Delete them", on_click=lambda: delete_legacy(legacy)).props("flat dense")

        async def download(name, status_label):
            status_label.set_text(f"Downloading {name}...")
            status_label.classes("text-warning", remove="text-grey")
            try:
                await run.io_bound(download_model, name, models_root)
            except Exception as e:
                status_label.set_text(f"Download failed: {e}")
                status_label.classes("text-negative", remove="text-warning")
                ui.notify(f"Whisper {name} download failed: {e}", type="negative")
                return
            rows.refresh()

        def delete_legacy(paths):
            for p in paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            rows.refresh()

        rows()


def _translation_section():
    from Translation import offline_translation as ot

    names = ot.language_names()

    def label(p):
        return f"{p['from_name']} \u2192 {p['to_name']} ({_human_bytes(p['size'])})"

    with ui.card().classes("w-full mt-4"):
        ui.label("Translation Models (Argos Translate)").classes("text-h5")
        ui.label(f"Install location: {ot.translation_root()}").classes("text-caption")
        ui.label(
            "One model per direction. Pairs without a direct model translate through English."
            " Licenses vary by model: most are derived from OPUS-MT (CC-BY 4.0); see each"
            " model's README after installing."
        ).classes("text-caption text-grey")

        @ui.refreshable
        def installed_view():
            pairs = sorted(ot.installed_pairs(), key=lambda p: (names.get(p[0], p[0]), names.get(p[1], p[1])))
            ui.label(f"Installed ({len(pairs)}):").classes("text-subtitle2")
            with ui.row().classes("gap-1"):
                for a, b in pairs:
                    with ui.chip(f"{names.get(a, a)} \u2192 {names.get(b, b)}", color="positive",
                                 removable=True).props("outline dense") as chip:
                        chip.on("remove", lambda _e, a=a, b=b: remove(a, b))

        installed_view()

        def options():
            have = ot.installed_pairs()
            return {p["code"]: label(p) for p in ot.load_index() if (p["from_code"], p["to_code"]) not in have}

        picker = ui.select(options(), multiple=True, with_input=True,
                           label="Choose models to download (type to filter)").classes("w-full").props("use-chips")
        state = {"done": 0, "total": None, "current": "", "busy": False}
        progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
        progress.set_visibility(False)
        status = ui.label("").classes("text-caption")

        def _tick():
            if state["busy"]:
                progress.set_value(state["done"] / state["total"] if state["total"] else 0)
                status.set_text(f"Downloading {state['current']}: {_human_bytes(state['done'])}"
                                f" of {_human_bytes(state['total'])}")

        ui.timer(0.25, _tick)

        async def download_selected():
            codes = list(picker.value or [])
            if not codes or state["busy"]:
                return
            by_code = {p["code"]: p for p in ot.load_index()}
            state["busy"] = True
            progress.set_visibility(True)
            failures = []
            for code in codes:
                p = by_code[code]
                state.update(done=0, total=p["size"], current=label(p))
                try:
                    await run.io_bound(ot.download_package, p["from_code"], p["to_code"], None,
                                       lambda d, t: state.update(done=d, total=t))
                except Exception as e:
                    failures.append(f"{label(p)}: {e}")
            state["busy"] = False
            progress.set_visibility(False)
            picker.set_options(options(), value=[])
            installed_view.refresh()
            if failures:
                status.set_text("Failed \u2014 " + "; ".join(failures))
                ui.notify("Some downloads failed: " + "; ".join(failures), type="negative", multi_line=True)
            else:
                status.set_text(f"Installed {len(codes)} model(s)")

        def remove(a, b):
            ot.remove_package(a, b)
            picker.set_options(options(), value=picker.value)
            installed_view.refresh()

        ui.button("Download selected", icon="download", on_click=download_selected).props("flat")


def _ner_section():
    from NLP.ner_onnx import NER_MODELS, download_model, is_model_installed

    with ui.card().classes("w-full mt-4"):
        ui.label("Named Entity Model (NER, Relationships)").classes("text-h5")
        ui.label(f"Install location: {os.path.join(get_models_dir(), 'ner')}").classes("text-caption")

        @ui.refreshable
        def rows():
            for key, info in NER_MODELS.items():
                installed = is_model_installed(key)
                with ui.row().classes("items-center w-full"):
                    ui.label(f"{info['name']} ({info['size']})").classes("w-80")
                    status = ui.label("Installed" if installed else "Not installed").classes(
                        "text-positive" if installed else "text-grey")
                    if not installed:
                        ui.button("Download", on_click=lambda k=key, sl=status: download(k, sl)).props("flat dense")
                ui.label(
                    f"{info['languages']}. Labels: {', '.join(info['labels'])}. License: {info['license']}."
                ).classes("text-caption ml-2")

        async def download(key, status_label):
            status_label.set_text("Downloading...")
            status_label.classes("text-warning", remove="text-grey")
            try:
                await run.io_bound(download_model, key)
            except Exception as e:
                status_label.set_text(f"Download failed: {e}")
                status_label.classes("text-negative", remove="text-warning")
                ui.notify(f"NER model download failed: {e}", type="negative")
                return
            rows.refresh()

        rows()


async def _download_qwen_model(model: dict, status_label: ui.label):
    """Download a Qwen GGUF model from HuggingFace."""
    from huggingface_hub import hf_hub_download

    status_label.set_text(f"Downloading {model['name']}...")
    status_label.classes("text-warning", remove="text-grey")

    def do_download():
        hf_hub_download(
            repo_id=model["repo_id"],
            filename=model["filename"],
            local_dir=get_models_dir(),
        )

    try:
        await run.io_bound(do_download)
        status_label.set_text("Installed")
        status_label.classes("text-positive", remove="text-warning")
    except Exception as e:
        status_label.set_text(f"Download failed: {e}")
        status_label.classes("text-negative", remove="text-warning")
        # Clean up partial download if it exists
        partial_path = os.path.join(get_models_dir(), model["filename"])
        if os.path.exists(partial_path):
            try:
                os.remove(partial_path)
            except OSError:
                pass


def downloads_page():
    ui.label("Downloads & Models").classes("text-h4")
    ui.label("Manage optional assets. Downloads come from official sources.").classes("text-subtitle1")
    ui.separator()

    _tessdata_section()
    _whisper_section()

    _translation_section()
    _ner_section()

    # LLM Models (Qwen 3.5)
    with ui.card().classes("w-full mt-4"):
        ui.label("LLM Models (RAG Chat)").classes("text-h5")
        ui.label(f"Install location: {get_models_dir()}").classes("text-caption")

        from RAG.hardware import detect_hardware
        hw_info = detect_hardware()

        hw_text = f"{hw_info.gpu_type.upper()} GPU — {hw_info.vram_mb} MB VRAM" if hw_info.gpu_available else f"No GPU — {hw_info.ram_mb} MB RAM"
        ui.label(f"Detected: {hw_text}").classes("text-caption")

        qwen_models = [
            {
                "name": "Qwen3.5-0.8B-Q4_K_M",
                "filename": "Qwen3.5-0.8B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-0.8B-GGUF",
                "size": "~533 MB",
                "desc": "Best for systems with < 2 GB available",
                "key": "0.8B",
            },
            {
                "name": "Qwen3.5-2B-Q4_K_M",
                "filename": "Qwen3.5-2B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-2B-GGUF",
                "size": "~1.28 GB",
                "desc": "Good balance for 2–4 GB systems",
                "key": "2B",
            },
            {
                "name": "Qwen3.5-4B-Q4_K_M",
                "filename": "Qwen3.5-4B-Q4_K_M.gguf",
                "repo_id": "unsloth/Qwen3.5-4B-GGUF",
                "size": "~2.74 GB",
                "desc": "Best quality, requires 4+ GB",
                "key": "4B",
            },
        ]

        models_dir = get_models_dir()

        for model in qwen_models:
            model_path = os.path.join(models_dir, model["filename"])
            installed = os.path.exists(model_path)
            is_recommended = model["key"] == hw_info.recommended_model

            with ui.row().classes("items-center w-full"):
                label_text = f"{model['name']} ({model['size']})"
                if is_recommended:
                    label_text += " ★ Recommended"
                ui.label(label_text).classes("w-80")

                if installed:
                    size_mb = os.path.getsize(model_path) / (1024 * 1024)
                    ui.label(f"Installed ({size_mb:.0f} MB)").classes("text-positive")
                else:
                    status = ui.label("Not installed").classes("text-grey")
                    ui.button(
                        "Download",
                        on_click=lambda m=model, sl=status: _download_qwen_model(m, sl),
                    ).props("flat dense")

            ui.label(model["desc"]).classes("text-caption ml-2")
