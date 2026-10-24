"""Capture the README screenshots headlessly (Linux, browser mode).

    # in a separate environment with playwright and pillow (and `playwright install chromium`):
    python tests/dev/readme_screenshots.py --models ~/.local/share/mdmt --llm Qwen3.5-2B-Q4_K_M.gguf

Starts MDMT with a throwaway data folder under /tmp/mdmt-demo (its model
folders are links to --models, so nothing is downloaded), indexes the eval
corpus (python -m eval.fetch_corpus first) and writes:

  MDMT_Welcome.png             the Welcome page
  docs/images/ragbot.png       RAGBot answering with a citation
  docs/images/ragbot.gif       the same answer streaming in
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO = "/tmp/mdmt-demo"
QUESTION = "Where was Frederick Douglass born?"


def prepare(models: str, llm: str) -> tuple[str, str]:
    shutil.rmtree(DEMO, ignore_errors=True)
    data = os.path.join(DEMO, "data", "mdmt")
    os.makedirs(os.path.join(data, "models"))
    for sub in ("tessdata", "whisper_models"):
        if os.path.isdir(os.path.join(models, sub)):
            os.symlink(os.path.join(models, sub), os.path.join(data, sub))
    for sub in ("rag", "ner", "translation", llm):
        src = os.path.join(models, "models", sub)
        if os.path.exists(src):
            os.symlink(src, os.path.join(data, "models", sub))
    docs = os.path.join(DEMO, "Documents", "Slave narratives and pamphlets")
    os.makedirs(docs)
    for name in ("douglass_narrative.txt", "paine_common_sense.txt", "franklin_autobiography.txt"):
        shutil.copy(os.path.join(REPO, "eval", "corpus", name), docs)
    return os.path.join(DEMO, "data"), docs


def start_app(python: str, xdg: str):
    env = dict(os.environ, XDG_DATA_HOME=xdg, MDMT_NO_BROWSER="1")
    proc = subprocess.Popen([python, os.path.join(REPO, "app.py")], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        m = re.search(r"(http://127\.0\.0\.1:\d+)/\?(token=\S+)", line)
        if m:
            return proc, m.group(1), m.group(2)
    proc.kill()
    raise RuntimeError("MDMT did not start")


def save_gif(frames, path, width=800):
    from PIL import Image
    images = []
    for png in frames:
        im = Image.open(png).convert("RGB")
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        images.append(im.quantize(colors=48, method=Image.MEDIANCUT))
    durations = [360] * (len(images) - 3) + [1500, 2500, 3500]
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", required=True, help="an MDMT data folder with downloaded models (…/mdmt)")
    parser.add_argument("--llm", default="Qwen3.5-2B-Q4_K_M.gguf")
    parser.add_argument("--app-python", default=os.path.join(REPO, ".venv", "bin", "python"))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    xdg, docs = prepare(os.path.expanduser(args.models), args.llm)
    proc, base, token = start_app(args.app_python, xdg)
    frames_dir = os.path.join(DEMO, "frames")
    os.makedirs(frames_dir)
    os.makedirs(os.path.join(REPO, "docs", "images"), exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"{base}/welcome?{token}")
            page.wait_for_timeout(2000)
            page.screenshot(path=os.path.join(REPO, "MDMT_Welcome.png"))

            page.locator(".mdmt-nav .q-item").filter(has_text="RAGBot").first.click()
            page.get_by_label("Documents folder").fill(docs)
            page.get_by_role("button", name="Start").click()
            page.get_by_text("Ask me anything about them").wait_for(timeout=300000)
            box = page.get_by_placeholder("Ask a question about your documents...")
            box.click()
            box.type(QUESTION, delay=35)
            frames = []
            box.press("Enter")
            sources = page.get_by_text("Sources:")
            deadline = time.monotonic() + 180
            while sources.count() == 0 and time.monotonic() < deadline:
                path = os.path.join(frames_dir, f"{len(frames):03d}.png")
                page.screenshot(path=path)
                frames.append(path)
                page.wait_for_timeout(150)
            page.wait_for_timeout(600)
            page.screenshot(path=os.path.join(REPO, "docs", "images", "ragbot.png"))
            for _ in range(3):
                path = os.path.join(frames_dir, f"{len(frames):03d}.png")
                page.screenshot(path=path)
                frames.append(path)
            browser.close()
        save_gif(frames[:-3:3] + frames[-3:], os.path.join(REPO, "docs", "images", "ragbot.gif"))
    finally:
        proc.terminate()
        proc.wait(10)
    for name in ("MDMT_Welcome.png", "docs/images/ragbot.png", "docs/images/ragbot.gif"):
        print(f"{name}: {os.path.getsize(os.path.join(REPO, name)) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
