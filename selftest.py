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
    "NLP.relationship_extraction",
    "OCR.ocr_logic",
    "OCR.tessdata",
    "RAG.hardware",
    "RAG.qwen_rag",
    "Translation.googletranslateWrapper",
    "pages.about",
    "pages.audio",
    "pages.cowords",
    "pages.downloads",
    "pages.keywords",
    "pages.ner",
    "pages.ocr",
    "pages.rag",
    "pages.relationships",
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

        @self.check("torch presence (informational)")
        def _():
            import importlib.util
            return {"torch_importable": importlib.util.find_spec("torch") is not None}

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
