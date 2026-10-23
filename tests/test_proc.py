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
