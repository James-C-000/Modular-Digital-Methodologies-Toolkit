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


# Job panels refresh every 0.5 s and the sidebar's job list every 1 s, so
# assertions about a running job wait up to 3 s (retries=30); the default
# (0.3 s) failed now and then on a slow Windows runner.
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
    await user.should_see("1 of 3 file(s) — b.txt", retries=30)
    user.find(marker="nav:/about").click()
    await user.should_see("About MDMT")
    await user.should_see("Running", retries=30)                      # the sidebar lists the job
    user.find(marker="nav:/cowords").click()
    await user.should_see("1 of 3 file(s) — b.txt", retries=30)       # re-attached on return
    release.set()
    await user.should_see("Finished in", retries=50)
    await user.should_see("3 of 3 file(s) analysed.")
    assert job.status == "done"


@pytest.mark.anyio
async def test_cancel_stops_the_job(user):
    release = threading.Event()
    await user.open("/ner")
    job = _slow_job("ner", release)
    await user.should_see("1 of 3 file(s) — b.txt", retries=30)
    user.find(kind=ui.button, content="Cancel").click()
    assert job.cancelled
    release.set()
    await user.should_see("Stopped after", retries=50)


@pytest.mark.anyio
async def test_inputs_are_remembered_across_visits(user, app_data):
    await user.open("/keywords")
    user.find(kind=ui.textarea, content="Keywords, one per line").type("harbour\nmill")
    user.find(kind=ui.input, content="Input folder (PDFs, searched recursively)").type(str(app_data))
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
    user.find(kind=ui.input, content="Input folder (PDFs, searched recursively)").type(str(app_data / "pdfs"))
    user.find(kind=ui.input, content="Output folder").type(str(app_data / "pdfs" / "."))
    user.find(kind=ui.textarea, content="Keywords, one per line").type("mill")
    user.find(kind=ui.button, content="Search").click()
    await user.should_see("The output folder must differ from the input folder.")


@pytest.mark.anyio
async def test_downloads_survive_navigation_and_can_be_deleted(user, app_data, monkeypatch):
    from common import assets
    release = threading.Event()

    def fake_download(self, on_progress=None):          # writes a "Whisper tiny" model slowly
        folder = app_data / "whisper_models" / "tiny"
        folder.mkdir(parents=True, exist_ok=True)
        on_progress(30 * 10**6, 78 * 10**6)
        release.wait(10)
        for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
            (folder / name).write_bytes(b"x" * 1000)

    monkeypatch.setattr(assets.Asset, "download", fake_download)
    await user.open("/downloads")
    await user.should_see("Whisper models (Audio Transcription)")
    user.find(marker="download:whisper:tiny").click()
    await user.should_see("Whisper tiny — 30 MB of 78 MB", retries=30)
    user.find(marker="nav:/about").click()
    await user.should_see("About MDMT")
    user.find(marker="nav:/downloads").click()
    await user.should_see("Whisper tiny — 30 MB of 78 MB", retries=30)
    release.set()
    await user.should_see("Installed · 4 KB", retries=50)
    user.find(marker="delete:whisper:tiny").click()
    user.find(kind=ui.button, content="Delete").click()
    await user.should_see(marker="download:whisper:tiny", retries=20)
    assert not (app_data / "whisper_models" / "tiny").exists()


@pytest.mark.anyio
async def test_welcome_offers_the_recommended_setup(user):
    await user.open("/welcome")
    await user.should_see("Recommended setup")
    await user.should_see("Whisper small")
    await user.should_see("Download all")


@pytest.mark.anyio
async def test_a_broken_extraction_is_explained_on_every_page(user, monkeypatch):
    from common import bundle
    monkeypatch.setattr(bundle, "PROBLEM", bundle.EXTRACTION_HELP)
    await user.open("/rag")
    await user.should_see("does not keep symbolic links")


@pytest.mark.anyio
async def test_thinking_mode_raises_the_context_length_and_restores_it(user):
    await user.open("/rag")
    context = user.find(kind=ui.number, content="Context length")
    context.clear().type("8192")
    assert config.AppConfig().get("defaults.rag_context_window") == 8192
    user.find(kind=ui.switch, content="Thinking mode").click()
    await user.should_see("Context length set to 32768")
    assert config.AppConfig().get("defaults.rag_context_window") == 32768
    user.find(kind=ui.switch, content="Thinking mode").click()        # off again: back to 8192
    assert config.AppConfig().get("defaults.rag_context_window") == 8192


@pytest.mark.anyio
async def test_a_saved_short_context_is_raised_when_thinking_is_on(user):
    from pages.components import save
    save("defaults.rag_thinking_mode", True)
    save("defaults.rag_context_window", 8192)
    await user.open("/rag")
    await user.should_see("Context length set to 32768")
    assert config.AppConfig().get("defaults.rag_context_window") == 32768


@pytest.mark.anyio
@pytest.mark.parametrize("page, kind, result", [
    ("/cowords", "cowords", {"files": 1, "total": 2, "summary": "", "images": [],
                             "skipped": [{"input": "box/blank.txt", "message": "no text"}]}),
    ("/ner", "ner", {"files": 1, "total": 2, "summary": "",
                     "skipped": [{"input": "box/blank.txt", "message": "no text"}]}),
    ("/relationships", "relationships", {"status": "success", "relationship_count": 3, "file_count": 1,
                                         "skipped": [{"input": "box/blank.txt", "message": "no text"}]}),
])
async def test_finished_jobs_list_the_files_they_skipped(user, page, kind, result):
    await user.open(page)
    JOBS.start(kind, kind, lambda job: result, output_dir="/tmp")
    await user.should_see("box/blank.txt — no text", retries=30)


@pytest.mark.anyio
async def test_keyword_search_says_when_nothing_was_found(user):
    await user.open("/keywords")
    JOBS.start("keywords", "keywords", lambda job: {"files": 1, "total": 1, "hits": 0, "charts": []},
               output_dir="/tmp")
    await user.should_see("None of the keywords were found.", retries=30)


@pytest.mark.anyio
async def test_keyword_search_does_not_blame_the_keywords_when_every_pdf_was_skipped(user):
    await user.open("/keywords")
    JOBS.start("keywords", "keywords", lambda job: {
        "files": 0, "total": 1, "hits": 0, "charts": [],
        "skipped": [{"input": "scan.pdf", "message": "no text (scanned PDF? run OCR first)"}]}, output_dir="/tmp")
    await user.should_see("scan.pdf — no text (scanned PDF? run OCR first)", retries=30)
    await user.should_not_see("None of the keywords were found.")
