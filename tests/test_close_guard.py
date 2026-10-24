"""The native window asks before closing only while a job runs."""
import threading
import time

from common.close_guard import install
from common.jobs import JobManager


def test_confirm_close_follows_running_jobs():
    jobs, sent, release = JobManager(), [], threading.Event()
    install(jobs, sent.append)
    job = jobs.start("ocr", "OCR", lambda j: release.wait(5))
    assert sent == [True]
    other = jobs.start("audio", "Audio", lambda j: release.wait(5))   # still busy: nothing new to send
    assert sent == [True]
    release.set()
    deadline = time.monotonic() + 5
    while (job.running or other.running or len(sent) < 2) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert sent == [True, False]
