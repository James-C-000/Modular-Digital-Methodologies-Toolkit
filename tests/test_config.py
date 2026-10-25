import json
import pytest
from config import AppConfig, get_app_data_dir


def test_get_app_data_dir_returns_path():
    path = get_app_data_dir()
    assert isinstance(path, str)
    assert "mdmt" in path.lower()


def test_config_default_values():
    config = AppConfig.__new__(AppConfig)
    config._data = {}
    config._path = "/tmp/test_mdmt_config.json"
    assert config.get("last_page", "/welcome") == "/welcome"
    assert config.get("defaults.ocr_language", "eng") == "eng"


def test_config_set_and_get(tmp_path):
    config_path = str(tmp_path / "config.json")
    config = AppConfig(config_path)
    config.set("last_page", "/ocr")
    assert config.get("last_page") == "/ocr"


def test_config_nested_set_and_get(tmp_path):
    config_path = str(tmp_path / "config.json")
    config = AppConfig(config_path)
    config.set("defaults.ocr_language", "fra")
    assert config.get("defaults.ocr_language") == "fra"


def test_config_save_and_load(tmp_path):
    config_path = str(tmp_path / "config.json")
    config = AppConfig(config_path)
    config.set("last_page", "/ner")
    config.save()

    config2 = AppConfig(config_path)
    assert config2.get("last_page") == "/ner"


def test_config_exists_check(tmp_path):
    config_path = str(tmp_path / "config.json")
    config = AppConfig(config_path)
    assert not config.exists()
    config.save()
    assert config.exists()


def test_config_save_and_load_utf8(tmp_path):
    """Config should handle UTF-8 characters (e.g., accented names, CJK)."""
    config_path = str(tmp_path / "config.json")
    config = AppConfig(config_path)
    config.set("defaults.ocr_language", "français")
    config.set("user.name", "日本語テスト")
    config.save()

    config2 = AppConfig(config_path)
    assert config2.get("defaults.ocr_language") == "français"
    assert config2.get("user.name") == "日本語テスト"


def test_a_corrupt_config_is_set_aside_not_fatal(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"defaults": {"ocr_input_dir": "/scans"', encoding="utf-8")   # cut off mid-write
    config = AppConfig(str(path))
    assert config.get("defaults.ocr_input_dir") is None
    backups = list(tmp_path.glob("config.json.corrupt-*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8").startswith('{"defaults"')
    config.set("ui.dark_mode", True)
    config.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {"ui": {"dark_mode": True}}


def test_a_config_that_is_not_an_object_is_set_aside(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    assert AppConfig(str(path)).get("ui.dark_mode", False) is False


def test_save_replaces_the_file_atomically(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    AppConfig(str(path)).save()
    config = AppConfig(str(path))
    config.set("defaults.whisper_model", "small")

    def crash(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", crash)
    with pytest.raises(OSError):
        config.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {}      # the old file is intact
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]   # no temporary left behind


def test_a_config_that_cannot_be_read_for_a_moment_is_kept(tmp_path, monkeypatch):
    """A lock held by another program is not damage: the file stays, and is not saved over."""
    import builtins
    path = tmp_path / "config.json"
    path.write_text('{"defaults": {"ocr_input_dir": "/scans"}}', encoding="utf-8")
    real_open = builtins.open

    def locked(file, *args, **kwargs):
        if str(file) == str(path):
            raise PermissionError(13, "in use by another process")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", locked)
    config = AppConfig(str(path))
    monkeypatch.setattr(builtins, "open", real_open)
    assert config.get("defaults.ocr_input_dir") is None
    config.set("ui.dark_mode", True)
    config.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {"defaults": {"ocr_input_dir": "/scans"}}
    assert not list(tmp_path.glob("config.json.corrupt-*"))
