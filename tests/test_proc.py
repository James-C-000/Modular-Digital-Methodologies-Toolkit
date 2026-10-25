"""Console windows must not flash in the windowed Windows build."""


def test_ocrmypdf_subprocesses_are_windowless_on_windows(monkeypatch):
    import types
    from common import proc
    monkeypatch.setattr(proc.sys, "platform", "win32")
    monkeypatch.setattr(proc.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    seen = []
    fake = types.SimpleNamespace(subprocess_run=lambda *a, **k: seen.append(k),
                                 Popen=lambda *a, **k: seen.append(k))
    proc.hide_console_windows_in(fake)
    proc.hide_console_windows_in(fake)  # idempotent
    fake.subprocess_run(["tesseract"], env={})
    fake.Popen(["tesseract"], creationflags=0x200)
    assert seen == [{"env": {}, "creationflags": 0x08000000}, {"creationflags": 0x200}]


def test_the_patched_ocrmypdf_module_is_the_one_that_starts_processes():
    """ocrmypdf 17 moved its subprocess calls into ocrmypdf.subprocess._run; patching the package did nothing."""
    from OCR import ocr_logic
    module = ocr_logic.OCRMYPDF_SUBPROCESS_MODULE
    assert callable(getattr(module, "subprocess_run", None)) and callable(getattr(module, "Popen", None))
    source = open(module.__file__, encoding="utf-8").read()
    assert "subprocess_run(" in source and "Popen(" in source
