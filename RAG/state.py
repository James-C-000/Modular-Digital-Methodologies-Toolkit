"""App-level RAG state: one session per MDMT process.

It lives here, not in the page, so it (and its conversation) survives
navigating to other pages and back.  Setup (model downloads, LLM load, indexing)
also runs here so progress is not lost when the page is left.
"""
import threading
from dataclasses import dataclass, field


@dataclass
class Turn:
    question: str
    answer: object = None        # RAG.session.Answer once finished
    error: str | None = None


@dataclass
class SetupProgress:
    running: bool = False
    stage: str = ""
    done: int = 0
    total: int = 0
    current: str = ""
    error: str | None = None
    report: object = None        # RAG.index.UpdateReport


@dataclass
class RagState:
    session: object = None       # RAG.session.RagSession
    turns: list = field(default_factory=list)
    setup: SetupProgress = field(default_factory=SetupProgress)
    lock: threading.Lock = field(default_factory=threading.Lock)
    pending: Turn | None = None  # the question being answered, if any
    stream: dict = field(default_factory=lambda: {"thinking": "", "answer": ""})
    stop_event: threading.Event = field(default_factory=threading.Event)


STATE = RagState()


def start_session(settings, n_gpu_layers: int = 0, job=None):
    """Download models if needed, load the LLM and index the folder (blocking).

    *job* (common.jobs.Job), if given, mirrors the progress for the sidebar.
    """
    from RAG import models
    from RAG.session import RagSession

    progress = STATE.setup
    progress.running, progress.error, progress.report = True, None, None
    try:
        for info in (models.EMBEDDER, models.RERANKER) if settings.rerank else (models.EMBEDDER,):
            if not models.is_installed(info):
                progress.stage = f"Downloading {info['name']} ({info['size']})..."
                if job:
                    job.progress(0, 0, progress.stage)
                models.download(info)
        progress.stage = "Loading the language model..."
        if job:
            job.progress(0, 0, progress.stage)
        settings.n_gpu_layers = n_gpu_layers
        old, STATE.session = STATE.session, None
        if old is not None:
            old.close()
        session = RagSession(settings)
        progress.stage = "Indexing documents..."

        def on_progress(done, total, name):
            progress.done, progress.total, progress.current = done, total, name
            if job:
                job.progress(done, total, name)

        progress.report = session.build_index(on_progress)
        STATE.session, STATE.turns = session, []
        progress.stage = "Ready"
    except Exception as e:
        progress.error = str(e)
        progress.stage = "Failed"
        raise
    finally:
        progress.running = False


def answer(question: str, job=None):
    """Answer *question* in the current session, streaming into STATE.stream (blocking).

    The turn is STATE.pending while it runs and joins STATE.turns when done, so a
    page shown again mid-answer can pick up the stream.
    """
    turn = Turn(question)
    STATE.stream = {"thinking": "", "answer": ""}
    STATE.stop_event.clear()
    STATE.pending = turn

    def on_token(kind, text):
        STATE.stream[kind] += text

    try:
        if job:
            job.progress(0, 0, "Answering...")
        turn.answer = STATE.session.ask(question, on_token, STATE.stop_event)
    except Exception as e:
        turn.error = str(e)
    finally:
        STATE.turns.append(turn)
        STATE.pending = None
    return turn


def close_session():
    session, STATE.session = STATE.session, None
    STATE.turns = []
    if session is not None:
        session.close()
