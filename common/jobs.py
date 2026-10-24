"""App-level background jobs.

A job runs in a worker thread owned by this module, not by the page that
started it, so it keeps going when the user navigates elsewhere.  Pages and the
sidebar read its progress (files done/total, current file, elapsed time) and
can ask it to stop; the work function checks ``job.cancelled`` between files.

    job = JOBS.start("ocr", "OCR", lambda job: run_ocr_batch(..., on_progress=job.progress,
                                                             cancel=job.cancel_event),
                     output_dir=out_dir)
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger("mdmt.jobs")


class Busy(RuntimeError):
    """A job of the same kind is already running."""


@dataclass
class Job:
    kind: str                   # which page/feature owns it, e.g. "ocr"
    title: str
    output_dir: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "running"     # running, done, failed, cancelled
    done: int = 0
    total: int = 0
    current: str = ""
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    result: object = None
    summary: str = ""
    error: str | None = None
    images: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)   # free-form details for the page that owns the job
    cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def running(self) -> bool:
        return self.status == "running"

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    @property
    def elapsed(self) -> float:
        return (self.finished or time.monotonic()) - self.started

    @property
    def fraction(self) -> float | None:
        return self.done / self.total if self.total else None

    def progress(self, done: int, total: int, current: str = ""):
        """Progress callback for the processing functions: (files done, total, current file)."""
        self.done, self.total, self.current = done, total, current

    def add_image(self, path: str):
        self.images.append(path)

    def cancel(self):
        self.cancel_event.set()


class JobManager:
    def __init__(self):
        self._jobs: list[Job] = []
        self._lock = threading.Lock()
        self._listeners = []

    def start(self, kind: str, title: str, work, output_dir: str | None = None) -> Job:
        """Run ``work(job)`` in a background thread; its return value becomes ``job.result``."""
        with self._lock:
            if any(j.kind == kind and j.running for j in self._jobs):
                raise Busy(f"{title} is already running")
            job = Job(kind, title, output_dir)
            self._jobs = [j for j in self._jobs if j.kind != kind] + [job]  # keep the latest per kind
        threading.Thread(target=self._run, args=(job, work), name=f"job-{kind}", daemon=True).start()
        self._notify()
        return job

    def _run(self, job: Job, work):
        log.info("job %s (%s) started", job.kind, job.id)
        try:
            job.result = work(job)
            job.status = "cancelled" if job.cancelled else "done"
        except Exception as e:
            log.exception("job %s (%s) failed", job.kind, job.id)
            job.error, job.status = str(e) or e.__class__.__name__, "failed"
        finally:
            job.finished = time.monotonic()
            log.info("job %s (%s) %s after %.1fs", job.kind, job.id, job.status, job.elapsed)
            self._notify()

    def latest(self, kind: str) -> Job | None:
        with self._lock:
            return next((j for j in reversed(self._jobs) if j.kind == kind), None)

    def all(self) -> list[Job]:
        """The latest job of every kind."""
        with self._lock:
            return list(self._jobs)

    def running(self) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs if j.running]

    def on_change(self, callback):
        """Call *callback()* (from any thread) whenever a job starts or ends."""
        self._listeners.append(callback)

    def _notify(self):
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                log.exception("job listener failed")


JOBS = JobManager()
