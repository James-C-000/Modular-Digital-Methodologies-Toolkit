"""Keep the self-test's module list in sync with the source tree."""
import os

from selftest import SELF_TEST_MODULES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGES = ("pages", "OCR", "Audio_Transcription", "Translation", "NLP", "RAG", "Advanced_Keyword_Search")


def test_self_test_imports_every_application_module():
    found = set()
    for pkg in PACKAGES:
        for name in os.listdir(os.path.join(ROOT, pkg)):
            if name.endswith(".py") and name != "__init__.py":
                found.add(f"{pkg}.{name[:-3]}")
    assert set(SELF_TEST_MODULES) == found


def test_loaded_shared_libraries_lists_this_interpreters_libs():
    from selftest import loaded_shared_libraries
    import ctypes  # noqa: F401  (loads _ctypes)
    libs = loaded_shared_libraries()
    assert libs and all(isinstance(p, str) for p in libs)
