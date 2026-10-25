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


def test_the_window_gets_the_latest_value_in_order():
    """A job that fails at once asks for True then False; only False (the current state) may stick."""
    from common.close_guard import _NativeSender
    sent = []
    sender = _NativeSender(sent.append)
    sender.SPACING = 0.05
    sender.want(True)
    sender.want(False)
    sender.want(True)
    deadline = time.monotonic() + 5
    while sent[-1:] != [True] and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.2)
    assert sent[-1] is True and all(a != b for a, b in zip(sent, sent[1:]))
    sender.want(False)
    deadline = time.monotonic() + 5
    while sent[-1] is not False and time.monotonic() < deadline:
        time.sleep(0.01)
    assert sent[-1] is False
