import json
import os
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
