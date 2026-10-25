"""Settings shared by the three PyInstaller specs (mdmt-{linux,macos,windows}.spec).

Imported from the specs via ``sys.path.insert(0, os.path.join(SPECPATH, "packaging"))``.
Platform-specific parts (Tesseract discovery, app bundle, icons) stay in the
individual spec files.
"""
import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from selftest import SELF_TEST_MODULES  # noqa: E402


# LGPL-3.0 packages (dependencies of OCRmyPDF) are shipped as plain .py files
# in the application folder, not inside the compressed module archive, so that
# users can replace them with their own versions as the LGPL requires.
LGPL_SOURCE_MODULES = {"fpdf": "py", "img2pdf": "py"}


def read_version() -> str:
    with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as f:
        return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)


VERSION = read_version()

# UPX-compressed DLLs are a common antivirus false-positive trigger and can
# break some native libraries; the size saving is not worth it.
UPX = False


def common_datas() -> list:
    datas = [
        (os.path.join(ROOT, "LICENSE"), "."),
        (os.path.join(ROOT, "THIRD_PARTY_LICENSES"), "."),
        (os.path.join(ROOT, "NLP", "data"), os.path.join("NLP", "data")),
        (os.path.join(ROOT, "Translation", "argos_index.json"), "Translation"),
        # Inputs for `mdmt --self-test` (a few tens of KB).
        (os.path.join(ROOT, "tests", "fixtures", "ocr_sample.pdf"), "selftest_fixtures"),
        (os.path.join(ROOT, "tests", "fixtures", "speech_sample.mp3"), "selftest_fixtures"),
    ]
    datas += collect_data_files("nicegui")
    datas += collect_data_files("ocrmypdf")
    datas += collect_data_files("faster_whisper")  # Silero VAD model (assets/*.onnx)
    datas += collect_data_files("py3langid")      # language-ID model
    datas += collect_data_files("sacremoses")     # Moses tokenizer data (nonbreaking prefixes)
    try:
        import certifi
        datas.append((certifi.where(), "certifi"))
    except ImportError:
        pass
    return datas


def licenses_datas(workpath: str, platform: str, libraries=(), tesseract_dir: str | None = None) -> list:
    """The bundle's licences/ folder: every bundled component's own licence files (packaging/collect_licenses.py)."""
    from collect_licenses import collect_licenses
    return [(collect_licenses(os.path.join(workpath, "licenses"), platform, libraries, tesseract_dir), "licenses")]


def common_binaries() -> list:
    binaries = []
    # llama-cpp-python loads libllama/ggml with ctypes, invisible to analysis.
    binaries += collect_dynamic_libs("llama_cpp")
    binaries += collect_dynamic_libs("ctranslate2")
    return binaries


def common_hiddenimports() -> list:
    hidden = collect_submodules("nicegui")
    hidden += [
        "engineio.async_drivers.threading",
        "ocrmypdf",
        "ocrmypdf.builtin_plugins.tesseract_ocr",
        "ocrmypdf.builtin_plugins.ghostscript",
        "ocrmypdf.builtin_plugins.concurrency",
        "ocrmypdf.builtin_plugins.default_filters",
        "ocrmypdf.builtin_plugins.null_ocr",
        "ocrmypdf.builtin_plugins.optimize",
        "ocrmypdf.builtin_plugins.pypdfium",
        "faster_whisper",
        "ctranslate2",
        "av",
        "sentencepiece",
        "sacremoses",
        "py3langid",
        "networkx",
        "llama_cpp",
        "certifi",
        "selftest",
        "version",
    ]
    hidden += SELF_TEST_MODULES
    return hidden
