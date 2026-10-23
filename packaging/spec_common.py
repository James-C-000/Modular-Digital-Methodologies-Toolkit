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


def read_version() -> str:
    with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as f:
        return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)


VERSION = read_version()

# UPX-compressed DLLs are a common antivirus false-positive trigger and can
# break some native libraries; the size saving is not worth it.
UPX = False


def common_datas() -> list:
    datas = [
        (os.path.join(ROOT, "Advanced_Keyword_Search", "*.txt"), "Advanced_Keyword_Search"),
        (os.path.join(ROOT, "LICENSE"), "."),
        (os.path.join(ROOT, "THIRD_PARTY_LICENSES"), "."),
        (os.path.join(ROOT, "NLP", "data"), os.path.join("NLP", "data")),
        # Inputs for `mdmt --self-test` (a few tens of KB).
        (os.path.join(ROOT, "tests", "fixtures", "ocr_sample.pdf"), "selftest_fixtures"),
        (os.path.join(ROOT, "tests", "fixtures", "speech_sample.mp3"), "selftest_fixtures"),
    ]
    datas += collect_data_files("nicegui")
    datas += collect_data_files("ocrmypdf")
    datas += collect_data_files("faster_whisper")  # Silero VAD model (assets/*.onnx)
    try:
        import certifi
        datas.append((certifi.where(), "certifi"))
    except ImportError:
        pass
    return datas


def common_binaries() -> list:
    binaries = []
    # llama-cpp-python loads libllama/ggml with ctypes, invisible to analysis.
    binaries += collect_dynamic_libs("llama_cpp")
    binaries += collect_dynamic_libs("ctranslate2")
    return binaries


# Test executables shipped inside the torch wheel: never run, and they link
# against libraries the bundle checker cannot resolve.
_PRUNE_PREFIXES = ("torch/bin/", "torch/test/", "torch\\bin\\", "torch\\test\\")


def prune(analysis):
    """Drop files from an Analysis that must not ship (call before PYZ)."""
    analysis.binaries = [b for b in analysis.binaries if not b[0].startswith(_PRUNE_PREFIXES)]
    analysis.datas = [d for d in analysis.datas if not d[0].startswith(_PRUNE_PREFIXES)]
    return analysis


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
        "googletrans",
        "langchain",
        "langchain_community",
        "sentence_transformers",
        "transformers",
        "networkx",
        "llama_cpp",
        "certifi",
        "selftest",
        "version",
    ]
    hidden += SELF_TEST_MODULES
    return hidden
