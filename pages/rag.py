"""RAG chat page: grounded, cited answers about a folder of documents.

The session, the conversation and any answer being generated live in
RAG.state; setup and answers run as jobs (common.jobs).  Leaving the page and
coming back picks up where things are, including an answer still streaming.
"""
import os

from nicegui import run, ui

from common.jobs import JOBS
from config import get_models_dir
from pages.components import FolderField, hint, remember, saved, section, start_job


def rag_page():
    from RAG.state import STATE

    with ui.row().classes("w-full items-center no-wrap"):
        with ui.column().classes("gap-0"):
            ui.label("RAGBot").classes("text-h5 text-weight-medium")
            ui.label("Ask questions about your documents; answers cite the passages they rely on.") \
                .classes("text-body2 mdmt-muted")
        ui.space()
        actions = ui.row().classes("items-center gap-1")
    ui.separator().classes("q-my-sm")

    @ui.refreshable
    def content():
        actions.clear()
        if STATE.session is not None and not STATE.setup.running:
            with actions:
                ui.button("New conversation", icon="add_comment", on_click=new_conversation).props("flat dense no-caps")
                ui.button("Re-index", icon="sync", on_click=reindex).props("flat dense no-caps")
                ui.button("Change setup", icon="settings", on_click=change_setup).props("flat dense no-caps")
            _chat_ui(STATE, content.refresh)
        else:
            _setup_ui(STATE, on_ready=content.refresh)

    def idle():
        return STATE.session is not None and not STATE.session.busy and STATE.pending is None

    def new_conversation():
        if idle():
            STATE.session.reset_conversation()
            STATE.turns = []
            content.refresh()

    async def reindex():
        if not idle():
            return
        n = ui.notification("Updating the index...", spinner=True, timeout=None)
        report = await run.io_bound(STATE.session.build_index)
        n.dismiss()
        ui.notify(f"Index updated: {len(report.added)} new, {len(report.changed)} changed, "
                  f"{len(report.removed)} removed files ({report.chunks} chunks).", type="positive")

    def change_setup():
        if idle():
            from RAG.state import close_session
            close_session()
            content.refresh()

    content()


# ------------------------------------------------------------------- setup ----

def _setup_ui(state, on_ready):
    from RAG import models
    from RAG.hardware import detect_hardware
    from RAG.session import RagSettings

    hw = detect_hardware()
    with section("Documents"):
        docs = FolderField("Documents folder", "defaults.rag_documents_dir")
        hint("Supported formats: TXT, PDF, Markdown, HTML, CSV, JSON, DOCX. Later starts only re-read files"
             " that changed.")

    with section("Model"):
        hw_text = (f"{hw.gpu_type.upper()} GPU — {hw.vram_mb} MB VRAM" if hw.gpu_available
                   else f"No GPU — {hw.ram_mb} MB RAM")
        hint(f"Detected hardware: {hw_text}")
        models_dir = get_models_dir()
        ggufs = sorted(f for f in os.listdir(models_dir) if f.endswith(".gguf")) if os.path.isdir(models_dir) else []
        options = {os.path.join(models_dir, f): f for f in ggufs}
        last = saved("defaults.rag_model_path", "")
        default = last if last and os.path.exists(last) else None
        if default is None and ggufs:
            default = next((os.path.join(models_dir, f) for f in ggufs
                            if f"-{hw.recommended_model}-" in f or f"-{hw.recommended_model}." in f),
                           os.path.join(models_dir, ggufs[0]))
        if default and default not in options:
            options[default] = os.path.basename(default)
        with ui.row().classes("w-full items-start no-wrap gap-1"):
            model_select = remember(ui.select(options, value=default, label="Model file (.gguf)")
                                    .classes("flex-grow"), "defaults.rag_model_path")

            async def browse_model():
                from pages.pickers import pick_file
                path = await pick_file(model_select.value or models_dir, [".gguf"], "GGUF models")
                if path:
                    model_select.set_options({**model_select.options, path: os.path.basename(path)}, value=path)

            ui.button(icon="description", on_click=browse_model).props("flat round").classes("q-mt-sm") \
                .tooltip("Browse...")
        if not ggufs:
            with ui.row().classes("items-center gap-1"):
                ui.label("No models found.").classes("text-warning")
                ui.button("Get a Qwen model", icon="download", on_click=lambda: ui.navigate.to("/downloads")) \
                    .props("flat dense no-caps")
        else:
            hint("Larger models (2B, 4B) answer more accurately than 0.8B but are slower and need more memory;"
                 " get them from the Downloads page.")

    with section("Options"):
        with ui.row().classes("items-center"):
            ctx_length = remember(ui.number("Context length", value=saved("defaults.rag_context_window", 8192),
                                            min=2048, max=65536, step=1024).classes("w-48"),
                                  "defaults.rag_context_window") \
                .tooltip("Longer contexts use more memory. 8192 is enough for six passages and a conversation.")
            thinking = remember(ui.switch("Thinking mode", value=saved("defaults.rag_thinking_mode", False)),
                                "defaults.rag_thinking_mode") \
                .tooltip("The model reasons before answering: slower, sometimes better on hard questions.")
            rerank = remember(ui.switch("Rerank passages", value=saved("defaults.rag_rerank", True)),
                              "defaults.rag_rerank") \
                .tooltip("A cross-encoder re-orders the best 20 passages: more accurate, a few seconds slower.")
        needed = [m for m in (models.EMBEDDER, models.RERANKER) if not models.is_installed(m)]
        if needed:
            hint("First start downloads: " + ", ".join(f"{m['name']} ({m['size']})" for m in needed))

    with ui.row().classes("w-full items-center no-wrap"):
        start_btn = ui.button("Start", icon="play_arrow").props("color=primary unelevated")
        status = ui.label("").classes("text-body2 q-ml-sm")
    progress = ui.linear_progress(value=0, show_value=False).classes("w-full")
    progress.set_visibility(False)
    shown_error = {"id": None}

    def tick():
        s, job = state.setup, JOBS.latest("rag-setup")
        if s.running:
            start_btn.disable()
            progress.set_visibility(True)
            if s.stage.startswith("Indexing") and s.total:
                progress.props(remove="indeterminate")
                progress.set_value(s.done / s.total)
                status.set_text(f"{s.stage} {s.done}/{s.total} {s.current}")
            else:
                progress.props("indeterminate")
                status.set_text(s.stage)
        elif state.session is not None:
            on_ready()
        else:
            start_btn.enable()
            progress.set_visibility(False)
            if job and job.status == "failed" and shown_error["id"] != job.id:
                shown_error["id"] = job.id
                status.set_text(f"Failed: {job.error}")
                status.classes("text-negative")

    ui.timer(0.3, tick)

    def start():
        if state.setup.running:
            return
        if not docs.value or not os.path.isdir(docs.value):
            return docs.error("Choose the folder of documents to ask about.")
        if not model_select.value or not os.path.exists(model_select.value):
            return ui.notify("Choose a model file.", type="warning")
        settings = RagSettings(documents_dir=docs.value, llm_path=model_select.value,
                               n_ctx=int(ctx_length.value or 8192), enable_thinking=thinking.value,
                               rerank=rerank.value)
        from RAG.state import start_session
        status.classes(remove="text-negative")
        state.setup.running, state.setup.stage = True, "Starting..."   # shown at once; start_session takes over
        if start_job("rag-setup", "RAG setup", lambda job: start_session(settings, hw.n_gpu_layers, job)) is None:
            state.setup.running = False

    start_btn.on_click(start)


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
            self.score = ui.label("").classes("text-caption mdmt-muted")
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
    from RAG.prompting import not_found_remainder
    answer = turn.answer
    if turn.error:
        ui.label(f"Error: {turn.error}").classes("text-negative")
        return
    if answer.thinking:
        with ui.expansion("Reasoning", icon="psychology").classes("w-full text-caption"):
            ui.label(answer.thinking).classes("whitespace-pre-wrap mdmt-muted")
    text = answer.text
    if answer.not_found:
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.icon("search_off")
            ui.label("Probably not in your documents.").classes("text-italic")
        text = not_found_remainder(text)
    if text or not answer.not_found:
        ui.markdown(text or "(no answer)")
    if answer.stopped:
        ui.label("Stopped.").classes("text-caption mdmt-muted")
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


def _chat_ui(state, refresh):
    session = state.session
    passages = PassageDialog(session.settings.documents_dir)
    with ui.column().classes("w-full mdmt-chat").style("height: calc(100vh - 150px); overflow: hidden"):
        with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0") as scroller:
            messages = ui.column().classes("w-full q-pa-sm")
        with ui.row().classes("w-full items-center no-wrap").style("flex-shrink: 0"):
            message_input = ui.input(placeholder="Ask a question about your documents...").classes("flex-grow")
            send_btn = ui.button("Send", icon="send").props("color=primary unelevated")
            stop_btn = ui.button("Stop", icon="stop").props("color=negative outline")

    with messages:
        report = state.setup.report
        n_files = len((session.index.manifest or {}).get("files", {}))
        ui.chat_message(f"I've indexed {n_files} document(s) ({len(session.index.chunks)} passages). "
                        "Ask me anything about them, ideally in the language they are written in.",
                        name="Assistant", stamp="System")
        if report and report.failed:
            ui.label("Could not read: " + ", ".join(f for f, _e in report.failed)).classes("text-caption text-warning")
        for turn in state.turns:
            ui.chat_message(turn.question, name="You", sent=True)
            with ui.chat_message(name="Assistant"), ui.column().classes("w-full gap-1"):
                _render_answer(turn, passages)

    live = {"turn": None, "thinking": None, "answer": None}

    def show_pending(turn):
        with messages:
            ui.chat_message(turn.question, name="You", sent=True)
            # One column per message: Quasar draws a separate bubble for every child.
            with ui.chat_message(name="Assistant"), ui.column().classes("gap-1"):
                live["thinking"] = ui.label("").classes("whitespace-pre-wrap text-caption mdmt-muted")
                live["thinking"].set_visibility(False)   # an empty label would draw an empty bubble
                live["answer"] = ui.label("Searching the documents...").classes("whitespace-pre-wrap")
        live["turn"] = turn
        scroller.scroll_to(percent=1.0)

    def set_generating(on: bool):
        message_input.set_enabled(not on)
        send_btn.set_enabled(not on)
        stop_btn.set_visibility(on)

    def tick():
        pending = state.pending
        if live["turn"] is not None and pending is not live["turn"]:
            refresh()            # the answer finished: draw it with its sources
            return
        if pending is not None and live["turn"] is None:
            show_pending(pending)
        if pending is not None:
            if state.stream["thinking"]:
                live["thinking"].set_visibility(True)
                live["thinking"].set_text(state.stream["thinking"][-600:])
            if state.stream["answer"]:
                live["answer"].set_text(state.stream["answer"])
                scroller.scroll_to(percent=1.0)
        set_generating(pending is not None)

    def send(_=None):
        question = (message_input.value or "").strip()
        if not question or state.pending is not None or session.busy:
            return
        from RAG.state import answer
        message_input.set_value("")
        if start_job("rag", "RAGBot", lambda job: answer(question, job)):
            set_generating(True)

    tick()
    ui.timer(0.15, tick)
    scroller.scroll_to(percent=1.0)
    send_btn.on_click(send)
    message_input.on("keydown.enter", send)
    stop_btn.on_click(lambda: state.stop_event.set())
