"""App-level job manager: jobs outlive the page that started them."""
import threading
import time

import pytest

from common.jobs import Busy, JobManager


def _wait(job, timeout=5.0):
    deadline = time.monotonic() + timeout
    while job.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not job.running, f"job still running: {job.status}"


def test_a_job_reports_progress_and_its_result():
    jobs = JobManager()

    def work(job):
        for i, name in enumerate(["a.pdf", "b.pdf"]):
            job.progress(i, 2, name)
        job.progress(2, 2, "")
        return [{"status": "success"}, {"status": "error"}]

    job = jobs.start("ocr", "OCR", work, output_dir="/out")
    _wait(job)
    assert job.status == "done" and job.result == [{"status": "success"}, {"status": "error"}]
    assert (job.done, job.total) == (2, 2) and job.output_dir == "/out"
    assert job.elapsed >= 0 and job.finished is not None
    assert jobs.latest("ocr") is job


def test_cancel_stops_between_files():
    jobs = JobManager()
    started, release = threading.Event(), threading.Event()
    processed = []

    def work(job):
        for i in range(5):
            if job.cancelled:
                break
            processed.append(i)
            started.set()
            release.wait(1)
        return processed

    job = jobs.start("audio", "Audio", work)
    started.wait(1)
    job.cancel()
    release.set()
    _wait(job)
    assert job.status == "cancelled" and processed == [0]


def test_a_failure_is_kept_on_the_job():
    jobs = JobManager()

    def work(job):
        raise ValueError("no PDFs here")

    job = jobs.start("keywords", "Keywords", work)
    _wait(job)
    assert job.status == "failed" and job.error == "no PDFs here"


def test_one_running_job_per_kind():
    jobs = JobManager()
    release = threading.Event()
    job = jobs.start("ner", "NER", lambda j: release.wait(2))
    with pytest.raises(Busy):
        jobs.start("ner", "NER", lambda j: None)
    other = jobs.start("cowords", "Co-words", lambda j: None)   # other kinds are fine
    assert [j.kind for j in jobs.running()] in (["ner"], ["ner", "cowords"])
    release.set()
    _wait(job)
    _wait(other)
    assert jobs.running() == []


def test_progress_records_images_and_summary():
    jobs = JobManager()

    def work(job):
        job.add_image("/out/graph.png")
        job.summary = "3 files, 12 relationships"

    job = jobs.start("relationships", "Relationships", work)
    _wait(job)
    assert job.images == ["/out/graph.png"] and job.summary == "3 files, 12 relationships"


def test_listeners_hear_about_starts_and_ends():
    jobs = JobManager()
    seen, release = [], threading.Event()
    jobs.on_change(lambda: seen.append(len(jobs.running())))
    job = jobs.start("ocr", "OCR", lambda j: release.wait(2))
    assert seen == [1]
    release.set()
    _wait(job)
    deadline = time.monotonic() + 2
    while len(seen) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen == [1, 0]
