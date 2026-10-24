"""Installation self-test: ``mdmt --self-test [--self-test-out report.json]``.

Runs real work through every native component without opening a window,
writes a JSON report and returns a process exit code (0 = all checks passed).
CI runs it against the frozen, windowed executable on Linux, macOS and
Windows.

The most important part is provenance: the CI runners have Homebrew or
Chocolatey copies of Tesseract and friends installed, so a frozen build can
appear to work while actually using system tools.  The report records every
shared library loaded into this process and the binaries we launch, and when
frozen asserts that they come from inside the bundle (``sys._MEIPASS``).
"""
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

from common.proc import no_window_kwargs

# Every module under the application packages.  tests/test_selftest.py keeps
# this list in sync with the source tree (a frozen app can't list its sources).
SELF_TEST_MODULES = [
    "Advanced_Keyword_Search.advancedKeywordSearchLogic",
    "Audio_Transcription.transcription_logic",
    "NLP.co_word_analysis",
    "NLP.named_entity_recognition",
    "NLP.ner_onnx",
    "NLP.relationship_extraction",
    "NLP.text_utils",
    "OCR.ocr_logic",
    "OCR.tessdata",
    "RAG.chunking",
    "RAG.generation",
    "RAG.hardware",
    "RAG.index",
    "RAG.loaders",
    "RAG.models",
    "RAG.prompting",
    "RAG.qwen_rag",
    "RAG.search",
    "RAG.session",
    "RAG.state",
    "Translation.bpe",
    "Translation.offline_translation",
    "pages.about",
    "pages.audio",
    "pages.components",
    "pages.cowords",
    "pages.downloads",
    "pages.keywords",
    "pages.ner",
    "pages.ocr",
    "pages.pickers",
    "pages.rag",
    "pages.relationships",
    "pages.shell",
    "pages.translation",
    "pages.welcome",
]

# Shared libraries that must be loaded from the bundle in a frozen build.
_BUNDLED_LIB_MARKERS = ("llama", "ggml", "ctranslate2", "avcodec", "avformat", "onnxruntime")

# Install locations of the tools the CI runners provide.  Loading anything
# from here means the build is leaning on the build machine.
_FOREIGN_PREFIXES = (
    "/opt/homebrew/", "/usr/local/Cellar/", "/usr/local/opt/",
    "c:\\programdata\\chocolatey\\", "c:\\program files\\tesseract-ocr\\",
    "c:\\program files\\gs\\", "c:\\hostedtoolcache\\", "/opt/hostedtoolcache/",
    "/users/runner/hostedtoolcache/",
)

_MSVC_RUNTIME_PREFIXES = ("vcruntime140", "msvcp140", "vcomp140", "concrt140")

EXPECTED_OCR_WORD = "lighthouse"
EXPECTED_SPEECH_WORD = "magazine"


def _bundle_dir() -> str | None:
    if getattr(sys, "frozen", False):
        return os.path.normcase(os.path.realpath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))))
    return None


def _inside_bundle(path: str) -> bool:
    """True for files in the frozen app: _MEIPASS, or next to the executable
    (Windows/Linux: dist/mdmt/; macOS: MDMT.app/Contents/MacOS/)."""
    bundle = _bundle_dir()
    if bundle is None:
        return True
    real = os.path.normcase(os.path.realpath(path))
    exe_dir = os.path.normcase(os.path.realpath(os.path.dirname(sys.executable)))
    return real.startswith(bundle + os.sep) or real.startswith(exe_dir + os.sep)


def _is_core_system_library(path: str) -> bool:
    """Libraries every user's OS provides (and that must not be bundled)."""
    norm = os.path.normcase(path)
    base = os.path.basename(norm)
    if sys.platform == "win32":
        return norm.startswith(os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + os.sep)
    if sys.platform == "darwin":
        return norm.startswith(("/usr/lib/", "/system/library/")) or path.startswith("/System/")
    return base.startswith(("ld-linux", "libc.so", "libm.so", "libdl.so", "libpthread.so", "librt.so",
                            "libutil.so", "libresolv.so", "libnss_", "libgcc_s.so", "ld.so.cache",
                            "libgconv", "linux-vdso")) or "/gconv/" in norm


def _fixture(name: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "selftest_fixtures", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures", name)


def loaded_shared_libraries() -> list[str]:
    """Paths of every shared library mapped into this process."""
    libs = set()
    if sys.platform.startswith("linux"):
        with open("/proc/self/maps", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split(maxsplit=5)
                if len(parts) == 6 and ".so" in parts[5]:
                    libs.add(parts[5].strip())
    elif sys.platform == "darwin":
        import ctypes
        dyld = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        dyld._dyld_image_count.restype = ctypes.c_uint32
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        for i in range(dyld._dyld_image_count()):
            name = dyld._dyld_get_image_name(i)
            if name:
                libs.add(name.decode("utf-8", "replace"))
    elif sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.EnumProcessModulesEx.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
        ]
        psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        process = kernel32.GetCurrentProcess()
        needed = wintypes.DWORD()
        modules = (wintypes.HMODULE * 4096)()
        if psapi.EnumProcessModulesEx(process, modules, ctypes.sizeof(modules), ctypes.byref(needed), 0x03):
            count = min(needed.value // ctypes.sizeof(wintypes.HMODULE), len(modules))
            buf = ctypes.create_unicode_buffer(32768)
            for i in range(count):
                if psapi.GetModuleFileNameExW(process, modules[i], buf, len(buf)):
                    libs.add(buf.value)
    return sorted(libs)


def _app_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")]


def check_browser_server(work: str) -> dict:
    """Start a second MDMT in browser mode and probe its server from outside."""
    import re
    import socket
    import urllib.error
    import urllib.request

    import psutil

    env = dict(os.environ, MDMT_NO_BROWSER="1", MDMT_BROWSER="1",
               XDG_DATA_HOME=os.path.join(work, "xdg-data"))  # separate app data and instance lock
    proc = subprocess.Popen(_app_command(), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **no_window_kwargs())
    try:
        url, seen, deadline = None, [], time.time() + 120
        while time.time() < deadline and url is None:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            seen.append(line)
            m = re.search(r"(http://127\.0\.0\.1:(\d+)/\?token=([\w-]+))", line)
            if m:
                url, port, token = m.group(1), int(m.group(2)), m.group(3)
        if url is None:
            raise RuntimeError("server did not start:\n" + "".join(seen[-30:]))
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)

        listening = sorted({c.laddr.ip for c in psutil.Process(proc.pid).net_connections(kind="inet")
                            if c.status == psutil.CONN_LISTEN})
        if listening != ["127.0.0.1"]:
            raise RuntimeError(f"server listens on {listening}, expected only 127.0.0.1")

        lan_ip = None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.0.2.1", 9))  # TEST-NET-1: no packets are sent
                lan_ip = s.getsockname()[0]
        except OSError:
            pass
        if lan_ip and not lan_ip.startswith("127."):
            try:
                with socket.create_connection((lan_ip, port), timeout=2):
                    raise RuntimeError(f"server reachable on {lan_ip}")
            except OSError:
                pass

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = urllib.request.build_opener(NoRedirect)

        def status(path, headers=None):
            try:
                with opener.open(urllib.request.Request(base + path, headers=headers or {}), timeout=10) as r:
                    return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, dict(e.headers), e.read().decode("utf-8", "replace")

        no_token, _h, _b = status("/welcome")
        bad_host, _h, _b = status(f"/?token={token}", {"Host": f"evil.example:{port}"})
        redirect, headers, _b = status(f"/?token={token}")
        cookie = headers.get("Set-Cookie", headers.get("set-cookie", "")).split(";")[0]
        page, _h, body = status("/welcome", {"Cookie": cookie})
        problems = []
        if no_token != 403:
            problems.append(f"tokenless request returned {no_token}, expected 403")
        if bad_host != 400:
            problems.append(f"foreign Host header returned {bad_host}, expected 400")
        if redirect != 302 or not cookie.startswith("mdmt_token="):
            problems.append(f"token link returned {redirect} with cookie {cookie!r}")
        if page != 200 or "MDMT" not in body:
            problems.append(f"page with cookie returned {page}")
        if problems:
            raise RuntimeError("; ".join(problems))
        return {"listening": listening, "lan_ip_refused": lan_ip, "no_token": no_token,
                "bad_host": bad_host, "token_link": redirect, "with_cookie": page}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


class SelfTest:
    def __init__(self):
        self.checks = []
        self.binaries = {}
        self.info = {}

    def check(self, name):
        """Decorator-style runner: records pass/fail, timing and errors."""
        def run(fn):
            start = time.time()
            entry = {"name": name}
            try:
                detail = fn()
                entry.update(ok=True, detail=detail)
            except Exception as e:
                entry.update(ok=False, error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
            entry["seconds"] = round(time.time() - start, 2)
            self.checks.append(entry)
            return fn
        return run

    # -- individual checks -------------------------------------------------

    def run_all(self):
        work = tempfile.mkdtemp(prefix="mdmt-selftest-")

        @self.check("environment")
        def _():
            from common import launch, logs
            from version import __version__
            self.info.update(
                version=__version__,
                python=sys.version,
                platform=platform.platform(),
                machine=platform.machine(),
                frozen=bool(getattr(sys, "frozen", False)),
                bundle=_bundle_dir(),
                executable=sys.executable,
                stdio_originally_missing=list(logs.ORIGINALLY_MISSING_STREAMS),
                stdio_at_launch=launch.STDIO,
                tessdata_prefix=os.environ.get("TESSDATA_PREFIX"),
            )
            return self.info

        @self.check("import application modules")
        def _():
            failures = {}
            for mod in SELF_TEST_MODULES:
                try:
                    importlib.import_module(mod)
                except Exception as e:
                    failures[mod] = f"{type(e).__name__}: {e}"
            if failures:
                raise RuntimeError(json.dumps(failures, indent=1))
            return f"{len(SELF_TEST_MODULES)} modules imported"

        @self.check("tesseract")
        def _():
            from OCR.tessdata import installed_languages
            exe = shutil.which("tesseract")
            if not exe:
                raise RuntimeError("tesseract not found on PATH")
            self.binaries["tesseract"] = exe
            version = subprocess.run([exe, "--version"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=60, **no_window_kwargs())
            langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=60, **no_window_kwargs())
            listed = set((langs.stdout + langs.stderr).split())
            managed = installed_languages()
            missing = {"eng", "osd"} - managed
            if missing:
                raise RuntimeError(f"managed tessdata dir lacks {sorted(missing)}")
            if not {"eng", "osd"} <= listed:
                raise RuntimeError(f"tesseract --list-langs does not show eng/osd: {langs.stdout}")
            libs = self._child_libraries(exe)
            self.binaries["tesseract_libraries"] = libs
            return {"version": version.stdout.splitlines()[:2], "list_langs": langs.stdout.splitlines()[:1],
                    "managed_languages": sorted(managed)}

        @self.check("ocr fixture")
        def _():
            from OCR.ocr_logic import run_ocr_file
            out_pdf = os.path.join(work, "ocr_out.pdf")
            sidecar = os.path.join(work, "ocr_out.txt")
            result = run_ocr_file(_fixture("ocr_sample.pdf"), out_pdf, ["eng"], sidecar_path=sidecar)
            if result["status"] != "success":
                raise RuntimeError(result.get("message"))
            with open(sidecar, encoding="utf-8") as f:
                text = f.read()
            if EXPECTED_OCR_WORD not in text.lower():
                raise RuntimeError(f"expected {EXPECTED_OCR_WORD!r} in OCR text, got {text!r}")
            return text.strip()

        @self.check("transcription fixture (faster-whisper tiny)")
        def _():
            from Audio_Transcription.transcription_logic import is_model_installed, load_model, transcribe_file
            from config import get_whisper_models_dir
            root = get_whisper_models_dir()
            downloaded = not is_model_installed("tiny", root)
            model = load_model("tiny", root)  # downloads through huggingface_hub/tqdm if needed
            result = transcribe_file(model, _fixture("speech_sample.mp3"), os.path.join(work, "speech.txt"))
            if result["status"] != "success":
                raise RuntimeError(result.get("message"))
            if EXPECTED_SPEECH_WORD not in result["text"].lower():
                raise RuntimeError(f"expected {EXPECTED_SPEECH_WORD!r} in transcript, got {result['text']!r}")
            import av
            codec = av._core.library_meta.get("libavcodec", {})
            gpl_flags = [f for f in codec.get("configuration", "").split()
                         if f in ("--enable-gpl", "--enable-nonfree") or "x264" in f or "x265" in f]
            if _bundle_dir() and (gpl_flags or not codec.get("license", "").startswith("LGPL")):
                # Releases must ship the LGPL-only FFmpeg (packaging/build_ffmpeg_lgpl.sh).
                raise RuntimeError(f"bundled FFmpeg is not LGPL-only: {codec.get('license')} {gpl_flags}")
            return {"text": result["text"], "downloaded_now": downloaded,
                    "ffmpeg": av.ffmpeg_version_info, "libavcodec_license": codec.get("license"),
                    "libavcodec_gpl_flags": gpl_flags}

        @self.check("named entities (multilingual ONNX)")
        def _():
            from NLP.ner_onnx import is_model_installed, load_model
            downloaded = not is_model_installed()
            ents = load_model().predict("In 1843 Ada Lovelace corresponded with Charles Babbage in London.")
            found = sorted({(e["entity_group"], e["word"]) for e in ents})
            if ("PER", "Ada Lovelace") not in found:
                raise RuntimeError(f"expected PER 'Ada Lovelace', got {found}")
            return {"entities": found, "downloaded_now": downloaded}

        @self.check("translation (Argos fr -> en)")
        def _():
            from Translation import offline_translation as ot
            downloaded = not ot.is_installed("fr", "en")
            ot.download_package("fr", "en")
            out = ot.translate_text("Le chat dort sur la chaise.", "fr", "en")
            if "cat" not in out.lower():
                raise RuntimeError(f"expected 'cat' in translation, got {out!r}")
            return {"translation": out, "downloaded_now": downloaded,
                    "detected": ot.detect_language("Le notaire a rédigé l'acte de vente.")}

        @self.check("co-words with stopwords")
        def _():
            from NLP.co_word_analysis import main as co_words
            folder = os.path.join(work, "cowords")
            os.makedirs(folder)
            with open(os.path.join(folder, "ledger.txt"), "w", encoding="utf-8") as f:
                f.write("The miller sold grain at the market. The miller paid the toll. " * 10)
            co_words(folder, stopword_language="en")
            with open(os.path.join(folder, "ledger_co_word_analysis.html"), encoding="utf-8") as f:
                report = f.read()
            if "<td>miller</td>" not in report or "<td>the</td>" in report:
                raise RuntimeError("stopwords were not applied")
            return {"report_bytes": len(report)}

        @self.check("llama.cpp")
        def _():
            import llama_cpp
            import llama_cpp.llama_cpp as lib
            handle = getattr(lib, "_lib", None)
            path = getattr(handle, "_name", None)
            if path:
                self.binaries["libllama"] = path
            info = lib.llama_print_system_info().decode("utf-8", "replace").strip()
            # The release must run on CPUs older than the CI runner's: it is built
            # with GGML_NATIVE=OFF (AVX2 baseline), so no AVX-512 code paths.
            # (A native build is fine for a developer's own source checkout.)
            if _bundle_dir() and platform.machine().lower() in ("x86_64", "amd64") and "AVX512 = 1" in info:
                raise RuntimeError("llama.cpp was compiled for the build machine's CPU (AVX-512): " + info)
            return {"version": llama_cpp.__version__, "library": path, "system_info": info}

        @self.check("matplotlib Agg render")
        def _():
            import matplotlib
            from matplotlib.figure import Figure
            fig = Figure(figsize=(2, 2))
            fig.subplots().plot([0, 1], [1, 0])
            out = os.path.join(work, "plot.png")
            fig.savefig(out)
            with open(out, "rb") as f:
                if f.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise RuntimeError("not a PNG")
            return {"backend": matplotlib.get_backend(), "bytes": os.path.getsize(out)}

        @self.check("ghostscript detection")
        def _():
            from OCR.ocr_logic import find_ghostscript
            gs = find_ghostscript()
            return {"ghostscript": gs, "pdfa_available": bool(gs)}

        @self.check("torch-free build")
        def _():
            import importlib.util
            present = [m for m in ("torch", "transformers", "sentence_transformers", "langchain", "faiss")
                       if importlib.util.find_spec(m) is not None]
            if present and _bundle_dir():
                raise RuntimeError(f"frozen build contains {present}")
            return {"importable": present}

        @self.check("RAG retrieval (e5-small + BM25)")
        def _():
            from RAG.index import CorpusIndex
            from RAG.models import get_embedder, is_installed, EMBEDDER
            downloaded = not is_installed(EMBEDDER)
            corpus = os.path.join(work, "rag-corpus")
            os.makedirs(corpus)
            docs = {"ledger.txt": "The brig Endeavour arrived from Lisbon carrying cork, salt and port wine. "
                                  "The harbour master Josiah Penrose recorded a duty of fourteen pounds.",
                    "mill.txt": "The mill flooded in the winter of 1751 and the bridge was carried away.",
                    "letters.txt": "Ada Lovelace corresponded with Charles Babbage about the Analytical Engine."}
            for name, text in docs.items():
                with open(os.path.join(corpus, name), "w", encoding="utf-8") as f:
                    f.write(text)
            index = CorpusIndex(corpus, get_embedder(), index_root=os.path.join(work, "rag-index"))
            report = index.update()
            hits = index.search("Which ship came from Portugal?", k=3)
            if not hits or hits[0].chunk.file != "ledger.txt":
                raise RuntimeError(f"expected ledger.txt first, got {[h.chunk.file for h in hits]}")
            return {"chunks": report.chunks, "top": [h.chunk.file for h in hits], "downloaded_now": downloaded}

        @self.check("browser mode: local server security")
        def _():
            from common.ui_mode import use_native_window
            if use_native_window():
                return "skipped: native-window platform"
            return check_browser_server(work)

        @self.check("bundled binaries and libraries")
        def _():
            libs = loaded_shared_libraries()
            self.binaries["loaded_libraries"] = libs
            problems = []
            for name in ("tesseract", "libllama"):
                path = self.binaries.get(name)
                if path and not _inside_bundle(path):
                    problems.append(f"{name} is outside the bundle: {path}")
            if _bundle_dir():
                # Only meaningful for frozen builds: a source run legitimately
                # uses the runner's Python and Homebrew/Chocolatey tools.
                for lib in libs + self.binaries.get("tesseract_libraries", []):
                    norm = os.path.normcase(lib)
                    if any(norm.lower().startswith(p) for p in _FOREIGN_PREFIXES):
                        problems.append(f"loaded from the build machine's tool install: {lib}")
                for lib in libs:
                    base = os.path.basename(lib).lower()
                    if any(m in base for m in _BUNDLED_LIB_MARKERS) and not _inside_bundle(lib):
                        problems.append(f"component library outside the bundle: {lib}")
                    # MSVC runtimes are not part of Windows; users may lack the redistributable.
                    if base.startswith(_MSVC_RUNTIME_PREFIXES) and not _inside_bundle(lib):
                        problems.append(f"MSVC runtime loaded from the system instead of the bundle: {lib}")
                for marker in ("llama", "ctranslate2", "avcodec"):
                    if not any(marker in os.path.basename(lib).lower() for lib in libs):
                        problems.append(f"expected a loaded {marker} library, found none")
            if problems:
                raise RuntimeError("\n".join(problems))
            bundled = [lib for lib in libs if _bundle_dir() and _inside_bundle(lib)]
            # Not failures, but worth seeing: libraries loaded from the OS that
            # are not part of the platform's core runtime (e.g. Pillow dlopens
            # libfribidi if the system happens to have it).
            outside = [lib for lib in libs if _bundle_dir() and not _inside_bundle(lib)
                       and not _is_core_system_library(lib)]
            return {"loaded": len(libs), "inside_bundle": len(bundled), "warnings_outside_bundle": outside}

        shutil.rmtree(work, ignore_errors=True)

    def _child_libraries(self, exe: str) -> list[str]:
        """Libraries a child binary loads (best effort, per platform)."""
        try:
            if sys.platform.startswith("linux") and shutil.which("ldd"):
                out = subprocess.run(["ldd", exe], capture_output=True, text=True, timeout=30)
                return [p.split("=>")[1].split("(")[0].strip()
                        for p in out.stdout.splitlines() if "=>" in p and "/" in p.split("=>")[1]]
            if sys.platform == "darwin":
                env = dict(os.environ, DYLD_PRINT_LIBRARIES="1")
                out = subprocess.run([exe, "--version"], capture_output=True, text=True, env=env, timeout=30)
                return [line.split("loaded:", 1)[1].strip()
                        for line in out.stderr.splitlines() if "loaded:" in line]
        except Exception:
            pass
        return []

    def report(self) -> dict:
        return {
            "ok": all(c["ok"] for c in self.checks),
            "info": self.info,
            "checks": self.checks,
            "binaries": self.binaries,
        }


def run_self_test(out_path: str | None = None) -> int:
    test = SelfTest()
    test.run_all()
    report = test.report()
    if out_path is None:
        from common.logs import get_log_dir
        out_path = os.path.join(get_log_dir(), "selftest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    summary = "\n".join(
        f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']} ({c['seconds']}s)"
        + ("" if c["ok"] else f"\n    {c['error']}") for c in report["checks"]
    )
    print(summary)
    print(f"Self-test {'passed' if report['ok'] else 'FAILED'}; report: {out_path}")
    import logging
    logging.getLogger("mdmt.selftest").info("self-test %s\n%s", "passed" if report["ok"] else "FAILED", summary)
    # Copy the app log next to the report so CI can upload both.
    for handler in logging.getLogger().handlers:
        handler.flush()
        if getattr(handler, "_mdmt", False):
            try:
                shutil.copyfile(handler.baseFilename, out_path + ".log")
            except OSError:
                pass
    return 0 if report["ok"] else 1
