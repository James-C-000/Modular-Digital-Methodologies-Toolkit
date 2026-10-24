"""RAG chat page: grounded, cited answers about a folder of documents."""
import os
import threading

from nicegui import run, ui

from config import AppConfig, get_models_dir
from pages.pickers import browse_dir


def rag_page():
    from RAG.state import STATE

    config = AppConfig()
    ui.query(".q-page").style("overflow: hidden")
    with ui.row().classes("w-full items-center"):
        ui.label("RAG Chat").classes("text-h4")
        ui.space()
        actions = ui.row().classes("items-center gap-1")
    ui.label("Ask questions about your documents; answers cite the passages they rely on.").classes("text-subtitle1")
    ui.separator()

    @ui.refreshable
    def content():
        actions.clear()
        if STATE.session is not None and not STATE.setup.running:
            with actions:
                ui.button("New conversation", icon="add_comment", on_click=new_conversation).props("flat dense")
                ui.button("Re-index", icon="sync", on_click=reindex).props("flat dense")
                ui.button("Change setup", icon="settings", on_click=change_setup).props("flat dense")
            _chat_ui(STATE)
        else:
            _setup_ui(config, STATE, on_ready=content.refresh)

    def new_conversation():
        if STATE.session is not None and not STATE.session.busy:
            STATE.session.reset_conversation()
            STATE.turns = []
            content.refresh()

    async def reindex():
        if STATE.session is None or STATE.session.busy:
            return
        n = ui.notification("Updating the index...", spinner=True, timeout=None)
        report = await run.io_bound(STATE.session.build_index)
        n.dismiss()
        ui.notify(f"Index updated: {len(report.added)} new, {len(report.changed)} changed, "
                  f"{len(report.removed)} removed files ({report.chunks} chunks).", type="positive")

    def change_setup():
        if STATE.session is not None and STATE.session.busy:
            return
        from RAG.state import close_session
        close_session()
        content.refresh()

    content()


# ------------------------------------------------------------------- setup ----

def _setup_ui(config, state, on_ready):
    from RAG import models
    from RAG.hardware import detect_hardware
    from RAG.session import RagSettings

    hw = detect_hardware()
    with ui.card().classes("w-full"):
        doc_dir = ui.input("Documents Directory", value=config.get("defaults.rag_documents_dir", "")).classes("w-full")
        ui.button("Browse...", on_click=lambda: browse_dir(doc_dir), icon="folder_open").props("flat")
        ui.label("Supported formats: TXT, PDF, Markdown, HTML, CSV, JSON, DOCX").classes("text-caption text-grey")
        hw_text = (f"{hw.gpu_type.upper()} GPU — {hw.vram_mb} MB VRAM" if hw.gpu_available
                   else f"No GPU — {hw.ram_mb} MB RAM")
        ui.label(f"Detected hardware: {hw_text}").classes("text-caption")

        models_dir = get_models_dir()
        ggufs = sorted(f for f in os.listdir(models_dir) if f.endswith(".gguf")) if os.path.isdir(models_dir) else []
        options = {os.path.join(models_dir, f): f for f in ggufs}
        saved = config.get("defaults.rag_model_path", "")
        default = saved if saved and os.path.exists(saved) else None
        if default is None and ggufs:
            default = next((os.path.join(models_dir, f) for f in ggufs
                            if f"-{hw.recommended_model}-" in f or f"-{hw.recommended_model}." in f),
                           os.path.join(models_dir, ggufs[0]))
        if default and default not in options:
            options[default] = os.path.basename(default)
        model_select = ui.select(options, value=default, label="Model File (.gguf)").classes("w-full")

        async def browse_model():
            from pages.pickers import pick_file
            path = await pick_file(model_select.value or models_dir, [".gguf"], "GGUF models")
            if path:
                model_select.set_options({**model_select.options, path: os.path.basename(path)}, value=path)

        ui.button("Browse...", on_click=browse_model, icon="folder_open").props("flat")
        if not ggufs:
            ui.label("No models found. Visit the Downloads page to get a Qwen model.").classes("text-warning")

        with ui.row().classes("items-center"):
            ctx_length = ui.number("Context Length", value=config.get("defaults.rag_context_window", 8192),
                                   min=2048, max=65536, step=1024).classes("w-48") \
                .tooltip("Longer contexts use more memory. 8192 is enough for six passages and a conversation.")
            thinking = ui.switch("Thinking mode", value=config.get("defaults.rag_thinking_mode", False)) \
                .tooltip("The model reasons before answering: slower, sometimes better on hard questions.")
            rerank = ui.switch("Rerank passages", value=config.get("defaults.rag_rerank", True)) \
                .tooltip("A cross-encoder re-orders the best 20 passages: more accurate, a few seconds slower.")

        needed = [m for m in (models.EMBEDDER, models.RERANKER) if not models.is_installed(m)]
        if needed:
            ui.label("First start downloads: " + ", ".join(f"{m['name']} ({m['size']})" for m in needed)
                     ).classes("text-caption text-grey")

        status = ui.label(state.setup.stage if state.setup.running else "").classes("text-caption")
        progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
        progress.set_visibility(state.setup.running)

        def tick():
            s = state.setup
            if s.running:
                progress.set_visibility(True)
                progress.set_value(s.done / s.total if s.total else 0)
                detail = f" {s.done}/{s.total} {s.current}" if s.stage.startswith("Indexing") and s.total else ""
                status.set_text(s.stage + detail)
            elif state.session is not None:
                on_ready()

        ui.timer(0.3, tick)

        async def start():
            if state.setup.running:
                return
            if not doc_dir.value or not os.path.isdir(doc_dir.value):
                ui.notify("Please select a documents directory.", type="warning")
                return
            if not model_select.value or not os.path.exists(model_select.value):
                ui.notify("Please select a valid model file.", type="warning")
                return
            settings = RagSettings(documents_dir=doc_dir.value, llm_path=model_select.value,
                                   n_ctx=int(ctx_length.value or 8192), enable_thinking=thinking.value,
                                   rerank=rerank.value)
            config.set("defaults.rag_documents_dir", doc_dir.value)
            config.set("defaults.rag_model_path", model_select.value)
            config.set("defaults.rag_context_window", settings.n_ctx)
            config.set("defaults.rag_thinking_mode", thinking.value)
            config.set("defaults.rag_rerank", rerank.value)
            config.set("last_page", "/rag")
            config.save()
            from RAG.state import start_session
            try:
                await run.io_bound(start_session, settings, hw.n_gpu_layers)
            except Exception as e:
                status.set_text(f"Error: {e}")
                progress.set_visibility(False)
                ui.notify(f"Failed to start RAG: {e}", type="negative", multi_line=True)
                return
            report = state.setup.report
            if report and report.failed:
                ui.notify(f"{len(report.failed)} file(s) could not be read: "
                          + ", ".join(f for f, _e in report.failed[:5]), type="warning", multi_line=True)
            on_ready()

        ui.button("Start", on_click=start, icon="play_arrow").props("color=primary")


# -------------------------------------------------------------------- chat ----

def _source_label(chunk) -> str:
    return f"{chunk.file}, p. {chunk.page}" if chunk.page else chunk.file


class PassageDialog:
    """One reusable dialog per chat view for showing a cited passage."""

    def __init__(self, documents_dir):
        from common.opener import open_external
        self.documents_dir = documents_dir
        self.path = None
        # no-refocus: otherwise Quasar moves focus back to the source chip when
        # the close animation ends, stealing keystrokes typed into the question box.
        with ui.dialog().props("no-refocus") as self.dialog, ui.card().classes("w-[44rem] max-w-full"):
            self.title = ui.label("").classes("text-h6")
            self.score = ui.label("").classes("text-caption text-grey")
            with ui.scroll_area().classes("w-full h-64 border rounded q-pa-sm"):
                self.text = ui.label("").classes("whitespace-pre-wrap")
            with ui.row().classes("w-full justify-end"):
                ui.button("Open file", icon="open_in_new",
                          on_click=lambda: open_external(self.path) if self.path else None).props("flat")
                ui.button("Close", on_click=self.dialog.close).props("flat")

    def show(self, citation):
        chunk = citation.chunk
        self.path = os.path.join(self.documents_dir, chunk.file)
        self.title.set_text(f"[{citation.number}] {_source_label(chunk)}")
        self.score.set_text(f"Reranker score: {citation.score:.2f}" if citation.score is not None else "")
        self.text.set_text(chunk.text)
        self.dialog.open()


def _render_answer(turn, passages):
    answer = turn.answer
    if turn.error:
        ui.label(f"Error: {turn.error}").classes("text-negative")
        return
    if answer.thinking:
        with ui.expansion("Reasoning", icon="psychology").classes("w-full text-caption"):
            ui.label(answer.thinking).classes("whitespace-pre-wrap text-grey")
    if answer.not_found:
        with ui.row().classes("items-center gap-1"):
            ui.icon("search_off").classes("text-grey")
            ui.label("Not found in the documents.").classes("text-grey")
    else:
        ui.markdown(answer.text or "(no answer)")
    if answer.stopped:
        ui.label("Stopped.").classes("text-caption text-grey")
    if answer.citations:
        with ui.row().classes("gap-1 items-center"):
            ui.label("Sources:").classes("text-caption")
            for c in answer.citations:
                ui.chip(f"[{c.number}] {_source_label(c.chunk)}", icon="description",
                        on_click=lambda c=c: passages.show(c)).props("outline dense clickable")
    uncited = [c for c in answer.context if c not in answer.citations]
    if uncited:
        with ui.expansion(f"{len(uncited)} other retrieved passage(s)").classes("w-full text-caption"):
            for c in uncited:
                ui.chip(f"[{c.number}] {_source_label(c.chunk)}",
                        on_click=lambda c=c: passages.show(c)).props("outline dense clickable")


def _chat_ui(state):
    session = state.session
    passages = PassageDialog(session.settings.documents_dir)
    with ui.column().classes("w-full").style("height: calc(100vh - 170px); overflow: hidden"):
        with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0") as scroller:
            messages = ui.column().classes("w-full q-pa-sm")
        with ui.row().classes("w-full items-center no-wrap").style("flex-shrink: 0"):
            message_input = ui.input(placeholder="Ask a question about your documents...").classes("flex-grow")
            send_btn = ui.button("Send", icon="send").props("color=primary")
            stop_btn = ui.button("Stop", icon="stop").props("color=negative outline")
            stop_btn.set_visibility(False)

    with messages:
        report = state.setup.report
        n_files = len((session.index.manifest or {}).get("files", {}))
        ui.chat_message(f"I've indexed {n_files} document(s) ({len(session.index.chunks)} passages). "
                        "Ask me anything about them.", name="Assistant", stamp="System")
        if report and report.failed:
            ui.label("Could not read: " + ", ".join(f for f, _e in report.failed)).classes("text-caption text-warning")
        for turn in state.turns:
            ui.chat_message(turn.question, name="You", sent=True)
            with ui.chat_message(name="Assistant"):
                _render_answer(turn, passages)

    generating = {"on": False}
    stop_event = threading.Event()

    def set_generating(on: bool):
        generating["on"] = on
        message_input.set_enabled(not on)
        send_btn.set_enabled(not on)
        stop_btn.set_visibility(on)

    async def send(_=None):
        question = (message_input.value or "").strip()
        if not question or generating["on"] or session.busy:
            return
        from RAG.state import Turn
        message_input.set_value("")
        set_generating(True)
        stop_event.clear()
        turn = Turn(question)
        buffer = {"thinking": "", "answer": ""}
        with messages:
            ui.chat_message(question, name="You", sent=True)
            reply = ui.chat_message(name="Assistant")
            with reply:
                thinking_label = ui.label("").classes("whitespace-pre-wrap text-caption text-grey")
                answer_label = ui.label("Searching the documents...").classes("whitespace-pre-wrap")
        scroller.scroll_to(percent=1.0)

        def on_token(kind, text):
            buffer[kind] += text

        def flush():
            if buffer["thinking"]:
                thinking_label.set_text(buffer["thinking"][-600:])
            if buffer["answer"]:
                answer_label.set_text(buffer["answer"])
                scroller.scroll_to(percent=1.0)

        timer = ui.timer(0.1, flush)
        try:
            turn.answer = await run.io_bound(session.ask, question, on_token, stop_event)
        except Exception as e:
            turn.error = str(e)
        finally:
            timer.cancel()
            set_generating(False)
        state.turns.append(turn)
        reply.clear()
        with reply:
            _render_answer(turn, passages)
        scroller.scroll_to(percent=1.0)

    send_btn.on_click(send)
    message_input.on("keydown.enter", send)
    stop_btn.on_click(lambda: stop_event.set())
