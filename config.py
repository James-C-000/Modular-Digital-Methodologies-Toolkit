import json
import os
import threading
import time

from platformdirs import user_data_dir

APP_NAME = "mdmt"


def _replace(src: str, dst: str, attempts: int = 5):
    """os.replace, retried briefly: on Windows it fails while another program has *dst* open."""
    for attempt in range(attempts):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.1)


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


def get_index_dir() -> str:
    path = os.path.join(get_app_data_dir(), "index")
    os.makedirs(path, exist_ok=True)
    return path


def get_tesseract_path() -> str:
    """Return the path to the Tesseract binary.

    When running as a frozen PyInstaller app, checks for a bundled binary first.
    Falls back to system PATH.
    """
    import shutil
    import sys

    # Check for bundled Tesseract in frozen app
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bin_dir = os.path.join(base, "tesseract_bin")
        exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
        bundled = os.path.join(bin_dir, exe_name)
        if os.path.isfile(bundled):
            return bundled

    # Fall back to system PATH
    return shutil.which("tesseract") or "tesseract"


class AppConfig:
    """Simple JSON config with dot-notation access for nested keys."""

    def __init__(self, path: str = None):
        self._path = path or os.path.join(get_app_data_dir(), "config.json")
        self._data = {}
        self._read_failed = False
        if os.path.exists(self._path):
            import logging
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("not a JSON object")
                self._data = data
            except OSError as e:
                # Locked by another program for a moment, say: the file may be fine, so it is
                # neither moved aside nor overwritten by save() with these defaults.
                self._read_failed = True
                logging.getLogger("mdmt").warning("settings file could not be read (%s); using defaults", e)
            except ValueError as e:
                # A damaged settings file must not stop MDMT from starting:
                # keep it for inspection and start from defaults.
                backup = f"{self._path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
                try:
                    os.replace(self._path, backup)
                except OSError:
                    backup = "(could not be moved)"
                logging.getLogger("mdmt").warning("settings file damaged (%s); moved to %s", e, backup)

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
        """Write config to disk atomically (a crash mid-write leaves the old file).

        Does nothing if the file existed but could not be read: saving would
        replace every other setting with the defaults.
        """
        if self._read_failed:
            import logging
            logging.getLogger("mdmt").warning("settings not saved: the settings file could not be read")
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = f"{self._path}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            _replace(tmp, self._path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def exists(self) -> bool:
        """Check if config file exists on disk."""
        return os.path.exists(self._path)
