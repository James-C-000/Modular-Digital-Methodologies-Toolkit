import json
import os
from platformdirs import user_data_dir

APP_NAME = "mdmt"


def get_app_data_dir() -> str:
    """Return the platform-appropriate app data directory, creating it if needed."""
    path = user_data_dir(APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_models_dir() -> str:
    path = os.path.join(get_app_data_dir(), "models")
    os.makedirs(path, exist_ok=True)
    return path


def get_tessdata_dir() -> str:
    path = os.path.join(get_app_data_dir(), "tessdata")
    os.makedirs(path, exist_ok=True)
    return path


def get_whisper_models_dir() -> str:
    path = os.path.join(get_app_data_dir(), "whisper_models")
    os.makedirs(path, exist_ok=True)
    return path


def get_nltk_data_dir() -> str:
    path = os.path.join(get_app_data_dir(), "nltk_data")
    os.makedirs(path, exist_ok=True)
    return path


def get_index_dir() -> str:
    path = os.path.join(get_app_data_dir(), "index")
    os.makedirs(path, exist_ok=True)
    return path


class AppConfig:
    """Simple JSON config with dot-notation access for nested keys."""

    def __init__(self, path: str = None):
        self._path = path or os.path.join(get_app_data_dir(), "config.json")
        self._data = {}
        if os.path.exists(self._path):
            with open(self._path, "r") as f:
                self._data = json.load(f)

    def get(self, key: str, default=None):
        """Get a value using dot notation (e.g., 'defaults.ocr_language')."""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value):
        """Set a value using dot notation."""
        keys = key.split(".")
        target = self._data
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def save(self):
        """Write config to disk."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    def exists(self) -> bool:
        """Check if config file exists on disk."""
        return os.path.exists(self._path)
