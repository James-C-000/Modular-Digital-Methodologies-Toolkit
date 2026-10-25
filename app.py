"""MDMT main application entry point (the UI itself is pages/shell.py)."""
import multiprocessing

# Must come first.  In a frozen build every multiprocessing child (NiceGUI's
# native-window process, ocrmypdf workers) re-executes this program;
# freeze_support() hands such a child to its target and exits, so it never
# reaches the imports and setup below.
multiprocessing.freeze_support()

import common.launch  # noqa: F401  (records the std streams we were started with)
import os

# Jobs run in worker threads.  matplotlib's default macOS backend must not be
# used off the main thread, so force the non-interactive Agg backend before
# anything can import matplotlib.
os.environ["MPLBACKEND"] = "Agg"

# Windowed builds launched without a console (double-click) have no
# stdout/stderr.  Route them to the log file now, before importing NiceGUI:
# its dependencies install their own stand-in streams on import, which would
# silently discard output (CI showed this on Windows).
if __name__ == "__main__":
    from common.logs import setup_logging
    setup_logging()

import argparse
import logging
import sys

from nicegui import ui, app

from common.opener import open_external
from common.ui_mode import use_native_window
from config import get_app_data_dir
from version import __version__

log = logging.getLogger("mdmt")


TITLE = f"MDMT {__version__} - Modular Digital Methodologies Toolkit"
LOCK_WAIT_SECONDS = 20   # how long a second launch waits for a starting instance to answer


@app.get('/_mdmt/ping')
async def _ping():
    """Lets a second launch confirm that this instance is alive (browser mode)."""
    return {'app': 'mdmt', 'version': __version__, 'pid': os.getpid()}


# Open external links in the system browser instead of navigating within pywebview
@app.get('/api/open-external')
async def _open_external_url(url: str):
    if url.startswith(("http://", "https://")):
        open_external(url)
    return {'ok': True}


ui.add_head_html('''<script>
document.addEventListener('click', function(e) {
    var link = e.target.closest('a');
    if (link && link.href &&
        (link.href.startsWith('http://') || link.href.startsWith('https://')) &&
        !link.href.startsWith(window.location.origin)) {
        e.preventDefault();
        e.stopPropagation();
        fetch('/api/open-external?url=' + encodeURIComponent(link.href));
    }
}, true);
</script>''', shared=True)


def _setup_frozen_env(base_path: str = None):
    """Configure environment for bundled assets when running as a frozen app."""
    if base_path is None:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    # --- Tesseract ---
    # Language data is handled by OCR.tessdata.configure_tessdata().
    tess_bin_dir = os.path.join(base_path, "tesseract_bin")
    if os.path.isdir(tess_bin_dir):
        os.environ["PATH"] = tess_bin_dir + os.pathsep + os.environ.get("PATH", "")
        if sys.platform == "linux":
            # Tesseract's bundled shared libs need to be discoverable via LD_LIBRARY_PATH
            os.environ["LD_LIBRARY_PATH"] = (
                tess_bin_dir + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
            )

    # --- SSL certificates ---
    # PyInstaller doesn't bundle system CA certs; point SSL at certifi's bundle.
    try:
        import certifi
        ca_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    except ImportError:
        pass


def _check_extraction():
    """Warn (log, terminal and an in-app banner) if the download was unpacked without its symlinks."""
    from common import bundle
    flattened = bundle.flattened_symlinks(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    if flattened:
        bundle.PROBLEM = bundle.EXTRACTION_HELP
        log.error("%d library symlinks were extracted as text files (e.g. %s)", len(flattened), flattened[:3])
        print(bundle.EXTRACTION_HELP, file=sys.stderr, flush=True)


def _append_user_tool_paths():
    """Let a frozen macOS app find user-installed tools such as Ghostscript.

    Apps launched from Finder get a minimal PATH without Homebrew.  The
    directories are appended, so bundled tools always win.
    """
    if sys.platform != "darwin":
        return
    path = os.environ.get("PATH", "").split(os.pathsep)
    for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
        if extra not in path and os.path.isdir(extra):
            path.append(extra)
    os.environ["PATH"] = os.pathsep.join(p for p in path if p)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="mdmt", description="Modular Digital Methodologies Toolkit")
    parser.add_argument("--self-test", action="store_true",
                        help="check the installation without opening a window, then exit")
    parser.add_argument("--self-test-out", metavar="PATH.json",
                        help="write the self-test report to this file")
    # parse_known_args: macOS may pass e.g. -psn_0_12345 to app bundles.
    args, _unknown = parser.parse_known_args(argv)
    return args


def main():
    """Initialize app data directory and start NiceGUI."""
    if multiprocessing.current_process().name != "MainProcess":
        # Defensive: a spawned child that somehow calls main() needs none of
        # the setup (see the __name__ guard at the bottom of this file).
        return

    args = _parse_args()

    from common.logs import setup_logging
    log_path = setup_logging()
    log.info("MDMT %s starting: pid=%d frozen=%s python=%s log=%s",
             __version__, os.getpid(), bool(getattr(sys, "frozen", False)),
             sys.version.split()[0], log_path)

    if getattr(sys, "frozen", False):
        _setup_frozen_env()
        _check_extraction()
    _append_user_tool_paths()

    get_app_data_dir()

    from OCR.tessdata import configure_tessdata
    log.info("TESSDATA_PREFIX=%s", configure_tessdata())

    from common.downloads import remove_stale_parts
    from config import get_models_dir, get_tessdata_dir, get_whisper_models_dir
    for folder in (get_tessdata_dir(), get_whisper_models_dir(), get_models_dir()):
        remove_stale_parts(folder)

    if args.self_test:
        from selftest import run_self_test
        sys.exit(run_self_test(args.self_test_out))

    if use_native_window():
        _run_native_window()
    else:
        _run_in_browser()


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_native_window():
    from common.local_server import LocalAccessMiddleware
    port = _free_port()
    app.add_middleware(LocalAccessMiddleware, port=port, token=None)  # Host check only
    app.native.window_args["text_select"] = True
    # Ask before closing while a job runs (common/close_guard.py), in MDMT's words.
    from common import close_guard
    from common.jobs import JOBS
    app.native.start_args["localization"] = {"global.quitConfirmation": close_guard.QUESTION}
    close_guard.install(JOBS, close_guard.send_to_native_window)
    from pages.shell import root
    ui.run(root, native=True, port=port, title=TITLE, window_size=(1200, 800), reload=False)


def _run_in_browser():
    """Linux: serve on 127.0.0.1 with a per-launch token and open the user's browser."""
    import atexit
    import threading

    from common import instance
    from common.local_server import LocalAccessMiddleware, new_token

    lock = instance.lock_path()
    port, token = _free_port(), new_token()
    # Claimed exclusively: of two launches at once (a double click), one starts the
    # server and the other opens a tab on it once it answers.
    claimed = instance.claim_lock(lock, port=port, token=token)
    if not claimed:
        existing = instance.running_instance_url(lock, wait=LOCK_WAIT_SECONDS)
        if existing:
            log.info("MDMT is already running; opening a new tab")
            print("MDMT is already running; opening it in your browser.", flush=True)
            if os.environ.get("MDMT_NO_BROWSER") != "1":
                open_external(existing)
            return
        instance.remove_lock(lock)   # left by an MDMT that crashed
        claimed = instance.claim_lock(lock, port=port, token=token)
    if not claimed:
        log.warning("another MDMT claimed the instance lock at the same time; starting anyway")
        instance.write_lock(lock, port=port, token=token)

    url = f"http://127.0.0.1:{port}/?token={token}"
    app.add_middleware(LocalAccessMiddleware, port=port, token=token)
    atexit.register(instance.clear_lock, lock)
    app.on_shutdown(lambda: instance.clear_lock(lock))
    if os.environ.get("MDMT_NO_BROWSER") != "1":
        threading.Thread(target=_open_when_ready, args=(port, url), daemon=True).start()
    print(f"MDMT {__version__} is running at:\n  {url}\n"
          "Use 'Quit MDMT' in the sidebar, or press Ctrl+C here, to stop it.", flush=True)
    from pages.shell import root
    ui.run(root, native=False, host="127.0.0.1", port=port, show=False, reload=False,
           title=TITLE, show_welcome_message=False)


def _open_when_ready(port: int, url: str, timeout: float = 30.0):
    """Open the browser once the server accepts connections."""
    import socket
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    open_external(url)


# Only when run as a script.  Multiprocessing re-imports this module as
# "__mp_main__" in spawned children and in Python 3.14's forkserver process
# (which still calls itself "MainProcess"); neither must run main().  NiceGUI
# only needs "__mp_main__" here for reload mode, which MDMT does not use.
if __name__ == "__main__":
    main()
