"""The app shell, driven by NiceGUI's simulated user (no browser needed).

Proves the Phase 4 promises: navigation never kills work, the sidebar shows
running jobs, pages remember their inputs and validate folders.
"""
import threading

import pytest
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation

import config
from common.jobs import JOBS
from pages.shell import root


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def app_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: str(tmp_path))
    yield tmp_path
    for job in JOBS.running():
        job.cancel()


@pytest.fixture
async def user():
    async with user_simulation(root=root) as user:
        yield user


def _slow_job(kind, release, files=("a.txt", "b.txt", "c.txt")):
    def work(job):
        job.progress(1, len(files), files[1])
        release.wait(10)
        job.progress(len(files), len(files), "")
        return {"files": len(files), "total": len(files), "summary": "", "images": []}
    return JOBS.start(kind, kind, work, output_dir="/tmp")


@pytest.mark.anyio
async def test_welcome_is_the_start_page(user):
    await user.open("/")
    await user.should_see("Welcome to MDMT")


@pytest.mark.anyio
async def test_a_running_job_survives_navigation(user):
    release = threading.Event()
    await user.open("/cowords")
    job = _slow_job("cowords", release)
    await user.should_see("1 of 3 file(s) — b.txt")
    user.find(marker="nav:/about").click()
    await user.should_see("About MDMT")
    await user.should_see("Running")                      # the sidebar lists the job
    user.find(marker="nav:/cowords").click()
    await user.should_see("1 of 3 file(s) — b.txt")       # re-attached on return
    release.set()
    await user.should_see("Finished in", retries=50)
    await user.should_see("3 of 3 file(s) analysed.")
    assert job.status == "done"


@pytest.mark.anyio
async def test_cancel_stops_the_job(user):
    release = threading.Event()
    await user.open("/ner")
    job = _slow_job("ner", release)
    await user.should_see("1 of 3 file(s) — b.txt")
    user.find(kind=ui.button, content="Cancel").click()
    assert job.cancelled
    release.set()
    await user.should_see("Stopped after", retries=50)


@pytest.mark.anyio
async def test_inputs_are_remembered_across_visits(user, app_data):
    await user.open("/keywords")
    user.find(kind=ui.textarea, content="Keywords, one per line").type("harbour\nmill")
    user.find(kind=ui.input, content="PDF folder").type(str(app_data))
    await user.open("/about")
    await user.open("/keywords")
    await user.should_see("harbour")
    assert config.AppConfig().get("defaults.keywords_input_dir") == str(app_data)


@pytest.mark.anyio
async def test_missing_folder_is_reported(user, app_data):
    await user.open("/cowords")
    user.find(kind=ui.input, content="Input folder").type(str(app_data / "nowhere"))
    user.find(kind=ui.button, content="Run analysis").click()
    await user.should_see("Folder not found.")
    assert JOBS.latest("cowords") is None or not JOBS.latest("cowords").running


@pytest.mark.anyio
async def test_output_inside_input_is_rejected_for_keywords_only_when_same(user, app_data):
    (app_data / "pdfs").mkdir()
    await user.open("/keywords")
    user.find(kind=ui.input, content="PDF folder").type(str(app_data / "pdfs"))
    user.find(kind=ui.input, content="Output folder").type(str(app_data / "pdfs" / "."))
    user.find(kind=ui.textarea, content="Keywords, one per line").type("mill")
    user.find(kind=ui.button, content="Search").click()
    await user.should_see("The output folder must differ from the input folder.")
