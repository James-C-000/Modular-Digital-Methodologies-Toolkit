"""Tests for cross-platform compatibility."""
import os
import platform
import sys
from unittest.mock import patch


APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def _app_source():
    with open(APP_PY, encoding="utf-8") as f:
        return f.read()


def _app_tree():
    import ast
    return ast.parse(_app_source())


def test_freeze_support_is_the_first_statement():
    """Frozen multiprocessing children must exit before any app setup runs."""
    import ast
    body = [n for n in _app_tree().body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]  # skip docstring
    assert isinstance(body[0], ast.Import) and body[0].names[0].name == "multiprocessing"
    call = body[1].value
    assert ast.unparse(call) == "multiprocessing.freeze_support()"


def test_start_method_is_not_overridden():
    """macOS must keep Python's default 'spawn'; forking is unsafe with system frameworks."""
    assert "set_start_method" not in _app_source()


def test_agg_backend_is_forced_before_heavy_imports():
    import ast
    body = _app_tree().body
    env_idx = next(i for i, n in enumerate(body) if 'os.environ["MPLBACKEND"] = "Agg"' in ast.unparse(n).replace("'", '"'))
    first_heavy = next(i for i, n in enumerate(body)
                       if isinstance(n, (ast.Import, ast.ImportFrom))
                       and any(m in ast.unparse(n) for m in ("nicegui", "matplotlib", "config", "pages")))
    assert env_idx < first_heavy


def test_main_does_nothing_in_a_spawned_child():
    """Source runs: NiceGUI's spawned window process re-imports app.py and calls main()."""
    import app
    with patch("multiprocessing.current_process") as cp, \
         patch("app._parse_args", side_effect=AssertionError("setup ran in child")):
        cp.return_value.name = "SpawnProcess-1"
        assert app.main() is None


def test_open_external_endpoint_rejects_non_http(monkeypatch):
    import asyncio
    import app
    opened = []
    monkeypatch.setattr(app, "open_external", opened.append)
    asyncio.run(app._open_external_url("file:///etc/passwd"))
    asyncio.run(app._open_external_url(r"C:\Windows\System32\calc.exe"))
    asyncio.run(app._open_external_url("https://example.org"))
    assert opened == ["https://example.org"]


def test_self_test_flags_parse():
    from app import _parse_args
    args = _parse_args(["--self-test", "--self-test-out", "r.json", "-psn_0_1234"])
    assert args.self_test and args.self_test_out == "r.json"


def test_get_tesseract_path_returns_string():
    """get_tesseract_path should return a string path."""
    from config import get_tesseract_path
    result = get_tesseract_path()
    assert isinstance(result, str)


def test_get_tesseract_path_frozen_prefers_bundled(tmp_path):
    """When running as a frozen app, bundled Tesseract should be preferred."""
    from config import get_tesseract_path
    bundled_dir = tmp_path / "tesseract_bin"
    bundled_dir.mkdir()
    if platform.system() == "Windows":
        tesseract_bin = bundled_dir / "tesseract.exe"
    else:
        tesseract_bin = bundled_dir / "tesseract"
    tesseract_bin.touch()

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
        result = get_tesseract_path()
        assert isinstance(result, str)


def test_setup_frozen_tesseract_env_sets_path(tmp_path):
    """setup_frozen_env should prepend Tesseract dir to PATH."""
    from app import _setup_frozen_env
    bundled_dir = tmp_path / "tesseract_bin"
    bundled_dir.mkdir()
    if platform.system() == "Windows":
        (bundled_dir / "tesseract.exe").touch()
    else:
        (bundled_dir / "tesseract").touch()
    tessdata_dir = tmp_path / "tessdata"
    tessdata_dir.mkdir()

    old_path = os.environ.get("PATH", "")
    try:
        _setup_frozen_env(str(tmp_path))
        assert str(bundled_dir) in os.environ["PATH"]
    finally:
        os.environ["PATH"] = old_path
        os.environ.pop("TESSDATA_PREFIX", None)


def test_main_runs_only_as_a_script():
    """Spawned children and the 3.14 forkserver import app.py as __mp_main__."""
    import ast
    guards = [ast.unparse(n.test) for n in _app_tree().body if isinstance(n, ast.If)]
    assert "__name__ == '__main__'" in guards
    assert not any("__mp_main__" in g for g in guards)
