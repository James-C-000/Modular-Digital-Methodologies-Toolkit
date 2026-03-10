# MDMT Web UI Conversion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert MDMT from a Pygubu/Tkinter desktop GUI to a NiceGUI web UI with pywebview native window, packaged as a PyInstaller executable.

**Architecture:** Replace all `*Window.py` + `.ui` files with NiceGUI page modules in `pages/`. Backend logic modules stay unchanged. Three modules (OCR, Audio, Translation) need business logic extracted from their window files first. A new `app.py` entry point provides sidebar navigation and page routing.

**Tech Stack:** NiceGUI, pywebview, platformdirs, huggingface_hub, PyInstaller

**Spec:** `docs/superpowers/specs/2026-03-09-web-ui-conversion-design.md`

---

## File Structure

```
MDMT/
├── app.py                              (CREATE) Entry point, sidebar layout, page routing
├── config.py                           (CREATE) Config loading/saving, app data paths
├── pages/                              (CREATE) NiceGUI page modules
│   ├── __init__.py                     (CREATE)
│   ├── welcome.py                      (CREATE) First-run welcome page
│   ├── ocr.py                          (CREATE) OCR processing page
│   ├── audio.py                        (CREATE) Audio transcription page
│   ├── translation.py                  (CREATE) Translation page
│   ├── keywords.py                     (CREATE) Advanced keyword search page
│   ├── ner.py                          (CREATE) Named entity recognition page
│   ├── relationships.py                (CREATE) Relationship extraction page
│   ├── cowords.py                      (CREATE) Co-word analysis page
│   ├── rag.py                          (CREATE) RAG chat page
│   ├── downloads.py                    (CREATE) Asset manager page
│   └── about.py                        (CREATE) Help / About / License page
├── OCR/
│   └── ocr_logic.py                    (CREATE) Extracted OCR business logic
├── Audio_Transcription/
│   └── transcription_logic.py          (CREATE) Extracted Whisper business logic
├── Translation/
│   ├── __init__.py                     (CREATE) Make importable as package
│   └── googletranslateWrapper.py       (MODIFY) Add LANGUAGE_CODES dict
├── tests/                              (CREATE)
│   ├── __init__.py                     (CREATE)
│   ├── test_config.py                  (CREATE) Config module tests
│   ├── test_ocr_logic.py              (CREATE) OCR logic extraction tests
│   ├── test_transcription_logic.py    (CREATE) Transcription logic extraction tests
│   └── test_translation_wrapper.py    (CREATE) Translation wrapper extension tests
├── requirements.txt                    (MODIFY) Update dependencies
├── mdmt.spec                           (CREATE) PyInstaller spec file
│
├── Advanced_Keyword_Search/            (UNCHANGED)
├── NLP/                                (UNCHANGED)
├── RAG/                                (UNCHANGED)
│
├── defaultWindow.py                    (DELETE after migration)
├── aksWindow.py                        (DELETE after migration)
├── ocrWindow.py                        (DELETE after migration)
├── audioTranscriptionWindow.py         (DELETE after migration)
├── translationWindow.py                (DELETE after migration)
├── nerWindow.py                        (DELETE after migration)
├── coWordAnalysisWindow.py             (DELETE after migration)
├── relationshipExtractionWindow.py     (DELETE after migration)
├── ragWindow.py                        (DELETE after migration)
├── *.ui                                (DELETE after migration)
```

---

## Chunk 1: Foundation & Proof of Concept

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```
matplotlib==3.10.0
ocrmypdf==16.8.0
pandas~=2.2.3
requests~=2.32.3
openpyxl~=3.2.0b1
openai-whisper~=20240930
langchain-community~=0.3.20
langchain~=0.3.22
langchain-core~=0.3.49
googletrans~=4.0.2
pypdf~=5.4.0
future~=1.0.0
nicegui~=2.14
pywebview~=5.3
platformdirs~=4.3
huggingface_hub~=0.28
pytest~=8.3
```

Note: `pygubu` removed. `nicegui`, `pywebview`, `platformdirs`, `huggingface_hub`, `pytest` added.

- [ ] **Step 2: Install updated dependencies**

Run: `source .venv/bin/activate && pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: update dependencies for NiceGUI web UI conversion"
```

---

### Task 2: Create config module

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write tests for config module**

Create `tests/__init__.py` (empty) and `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_config.py -v`
Expected: FAIL — `config` module does not exist yet.

- [ ] **Step 3: Implement config module**

Create `config.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add config module with app data directory management"
```

---

### Task 3: Proof of concept — NiceGUI + pywebview + file dialog

**Files:**
- Create: `poc_nicegui.py` (temporary, deleted after validation)

- [ ] **Step 1: Create proof-of-concept app**

Create `poc_nicegui.py`:

```python
"""Proof of concept: NiceGUI + pywebview native window + file dialog + background task."""
import asyncio
import time
from nicegui import ui, run, app


def select_file():
    """Open a native file dialog via pywebview."""
    import webview
    result = webview.windows[0].create_file_dialog(
        webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=('All Files (*.*)',)
    )
    if result:
        file_label.set_text(f"Selected: {result[0]}")
    else:
        file_label.set_text("No file selected")


async def run_background_task():
    """Demonstrate run.io_bound with progress feedback."""
    progress.set_visibility(True)
    status.set_text("Processing...")
    button.disable()

    def slow_task():
        time.sleep(3)
        return "Task completed successfully!"

    result = await run.io_bound(slow_task)
    status.set_text(result)
    progress.set_visibility(False)
    button.enable()


ui.label("MDMT Proof of Concept").classes("text-h4")
ui.separator()

ui.button("Select File (Native Dialog)", on_click=select_file)
file_label = ui.label("No file selected")

ui.separator()

button = ui.button("Run Background Task", on_click=run_background_task)
progress = ui.linear_progress().props("indeterminate")
progress.set_visibility(False)
status = ui.label("Ready")

ui.run(native=True, title="MDMT PoC", window_size=(800, 500))
```

- [ ] **Step 2: Run the PoC and manually verify**

Run: `source .venv/bin/activate && python poc_nicegui.py`

Verify:
1. A native window opens (not a browser tab)
2. Clicking "Select File" opens an OS-native file picker
3. Clicking "Run Background Task" shows progress and completes after 3s
4. The UI remains responsive during the background task

- [ ] **Step 3: Document PoC results**

If the PoC works, proceed. If any aspect fails, investigate and resolve before continuing. Key failure modes to watch for:
- `pywebview` not installed or missing GTK/WebKit dependencies on Linux
- `webview.windows[0]` not accessible from NiceGUI callbacks
- Native mode not working with the installed Python version

- [ ] **Step 4: Validate PyInstaller bundling of PoC**

Run: `source .venv/bin/activate && pip install pyinstaller && pyinstaller poc_nicegui.py --onefile --noconsole --name poc_mdmt`

Then run: `./dist/poc_mdmt`

Verify: The resulting binary opens a native window with the same NiceGUI UI. If PyInstaller bundling fails, investigate and resolve before continuing — this is a core assumption of the project.

- [ ] **Step 5: Delete PoC files and commit**

```bash
rm poc_nicegui.py poc_nicegui.spec
rm -rf build/ dist/
git add -A
git commit -m "chore: validate NiceGUI + pywebview + PyInstaller PoC (passed)"
```

---

## Chunk 2: Backend Extraction

### Task 4: Extract OCR business logic

**Files:**
- Create: `OCR/ocr_logic.py`
- Create: `OCR/__init__.py`
- Create: `tests/test_ocr_logic.py`

**Tessdata migration note:** The project currently has tessdata files in `OCR/tessdata/` (including `tessconfigs/`). Going forward, the canonical location is `~/.local/share/mdmt/tessdata/` (via `get_tessdata_dir()`). The OCR page (Task 9) should check both locations — first the app data directory, then fall back to the bundled `OCR/tessdata/` if present. This ensures existing users' tessdata works without re-downloading. The Downloads page handles new installs to the app data directory.

- [ ] **Step 1: Write tests for OCR logic extraction**

Create `tests/test_ocr_logic.py`:

```python
import os
import pytest
from OCR.ocr_logic import TESSERACT_LANGUAGES, find_pdfs_in_directory, build_ocr_params


def test_tesseract_languages_contains_english():
    assert "English" in TESSERACT_LANGUAGES
    assert TESSERACT_LANGUAGES["English"] == "eng"


def test_tesseract_languages_has_all_entries():
    assert len(TESSERACT_LANGUAGES) > 100


def test_find_pdfs_in_directory(tmp_path):
    # Create some test files
    (tmp_path / "doc1.pdf").write_text("fake pdf")
    (tmp_path / "doc2.pdf").write_text("fake pdf")
    (tmp_path / "readme.txt").write_text("not a pdf")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "doc3.pdf").write_text("fake pdf")

    pdfs = find_pdfs_in_directory(str(tmp_path))
    assert len(pdfs) == 3
    assert all(p.endswith(".pdf") for p in pdfs)


def test_find_pdfs_empty_directory(tmp_path):
    pdfs = find_pdfs_in_directory(str(tmp_path))
    assert pdfs == []


def test_build_ocr_params_basic():
    params = build_ocr_params(
        language_codes=["eng"],
        deskew=False,
        rotate_pages=False,
        rotate_threshold=15,
        redo_ocr=False,
        output_type="pdf",
        sidecar_path=None,
    )
    assert params["language"] == "eng"
    assert params["deskew"] is False
    assert params["rotate_pages"] is False
    assert params["output_type"] == "pdf"
    assert "sidecar" not in params
    assert "rotate_pages_threshold" not in params


def test_build_ocr_params_with_sidecar_and_rotation():
    params = build_ocr_params(
        language_codes=["eng", "fra"],
        deskew=True,
        rotate_pages=True,
        rotate_threshold=30,
        redo_ocr=False,
        output_type="pdfa",
        sidecar_path="/tmp/out.txt",
    )
    assert params["language"] == "eng+fra"
    assert params["sidecar"] == "/tmp/out.txt"
    assert params["rotate_pages_threshold"] == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_ocr_logic.py -v`
Expected: FAIL — `OCR.ocr_logic` does not exist.

- [ ] **Step 3: Implement OCR logic module**

Create `OCR/__init__.py` (empty) and `OCR/ocr_logic.py`:

```python
"""OCR business logic extracted from ocrWindow.py."""
import os
import shutil
import ocrmypdf

TESSERACT_LANGUAGES = {
    "Afrikaans": "afr",
    "Albanian": "sqi",
    "Amharic": "amh",
    "Arabic (Script)": "Arabic",
    "Arabic": "ara",
    "Armenian (Script)": "Armenian",
    "Armenian": "hye",
    "Assamese": "Assamese",
    "Azerbaijani - Cyrillic": "aze_cyrl",
    "Azerbaijani": "aze",
    "Basque": "eus",
    "Belarusian": "bel",
    "Bengali (Script)": "Bengali",
    "Bengali": "ben",
    "Bosnian": "bos",
    "Breton": "bre",
    "Bulgarian": "bul",
    "Burmese": "mya",
    "Canadian Aboriginal (Script)": "Canadian_Aboriginal",
    "Catalan/Valencian": "cat",
    "Cebuano": "ceb",
    "Central Khmer": "khm",
    "Cherokee (Script)": "Cherokee",
    "Cherokee": "chr",
    "Chinese Simplified": "chi_sim",
    "Chinese Traditional": "chi_tra",
    "Corsican": "cos",
    "Croatian": "hrv",
    "Cyrillic (Script)": "Cyrillic",
    "Czech": "ces",
    "Danish": "dan",
    "Devanagari (Script)": "Devanagari",
    "Dhivehi": "div",
    "Dutch/Flemish": "nld",
    "Dzongkha": "dzo",
    "English": "eng",
    "English, Middle, 1100-1500": "enm",
    "Esperanto": "epo",
    "Estonian": "est",
    "Ethiopic (Script)": "Ethiopic",
    "Faroese": "fao",
    "Filipino": "fil",
    "Finnish": "fin",
    "Fraktur (Script)": "Fraktur",
    "French": "fra",
    "French, Middle, ca.1400-1600": "frm",
    "Galician": "glg",
    "Georgian (Script)": "Georgian",
    "Georgian - Old": "kat_old",
    "Georgian": "kat",
    "German Fraktur Latin": "deu_latf",
    "German": "deu",
    "Greek (Script)": "Greek",
    "Greek, Ancient, to 1453": "grc",
    "Greek, Modern, 1453-": "ell",
    "Gujarati (Script)": "Gujarati",
    "Gujarati": "guj",
    "Gurmukhi (Script)": "Gurmukhi",
    "Haitian/Haitian Creole": "hat",
    "Han Simplified (Script)": "HanS",
    "Han Simplified - Vertical (Script)": "HanS_vert",
    "Han Traditional (Script)": "HanT",
    "Han Traditional - Vertical (Script)": "HanT_vert",
    "Hangul (Script)": "Hangul",
    "Hangul - Vertical (Script)": "Hangul_vert",
    "Hebrew (Script)": "Hebrew",
    "Hebrew": "heb",
    "Hindi": "hin",
    "Hungarian": "hun",
    "Icelandic": "isl",
    "Indonesian": "ind",
    "Inuktitut": "iku",
    "Irish": "gle",
    "Italian - Old": "ita_old",
    "Italian": "ita",
    "Japanese (Script)": "Japanese",
    "Japanese - Vertical (Script)": "Japanese_vert",
    "Japanese": "jpn",
    "Javanese": "jav",
    "Kannada (Script)": "Kannada",
    "Kannada": "kan",
    "Kazakh": "kaz",
    "Khmer (Script)": "Khmer",
    "Kirghiz/Kyrgyz": "kir",
    "Korean Vertical": "kor_vert",
    "Korean": "kor",
    "Kurdish Kurmanji": "kmr",
    "Lao (Script)": "Lao",
    "Lao": "lao",
    "Latin (Script)": "Latin",
    "Latin": "lat",
    "Latvian": "lav",
    "Lithuanian": "lit",
    "Luxembourgish": "ltz",
    "Macedonian": "mkd",
    "Malay": "msa",
    "Malayalam (Script)": "Malayalam",
    "Malayalam": "mal",
    "Maltese": "mlt",
    "Maori": "mri",
    "Marathi": "mar",
    "Math Equations": "equ",
    "Mongolian": "mon",
    "Myanmar (Script)": "Myanmar",
    "Nepali": "nep",
    "Norwegian": "nor",
    "Occitan, 1500-": "oci",
    "Odia (Script)": "Odia",
    "Oriya": "ori",
    "Panjabi/Punjabi": "pan",
    "Persian": "fas",
    "Polish": "pol",
    "Portuguese": "por",
    "Pushto/Pashto": "pus",
    "Quechua": "que",
    "Romanian/Moldavian/Moldovan": "ron",
    "Russian": "rus",
    "Sanskrit": "san",
    "Scottish Gaelic": "gla",
    "Serbian - Latin": "srp_latn",
    "Serbian": "srp",
    "Sindhi": "snd",
    "Sinhala (Script)": "Sinhala",
    "Sinhala/Sinhalese": "sin",
    "Slovak": "slk",
    "Slovenian": "slv",
    "Spanish/Castilian": "spa",
    "Spanish/Old Castilian": "spa_old",
    "Sundanese": "sun",
    "Swahili": "swa",
    "Swedish": "swe",
    "Syriac (Script)": "Syriac",
    "Syriac": "syr",
    "Tajik": "tgk",
    "Tamil (Script)": "Tamil",
    "Tamil": "tam",
    "Tatar": "tat",
    "Telugu (Script)": "Telugu",
    "Telugu": "tel",
    "Thaana (Script)": "Thaana",
    "Thai (Script)": "Thai",
    "Thai": "tha",
    "Tibetan (Script)": "Tibetan",
    "Tibetan": "bod",
    "Tigrinya": "tir",
    "Tonga": "ton",
    "Turkish": "tur",
    "Uighur/Uyghur": "uig",
    "Ukrainian": "ukr",
    "Urdu": "urd",
    "Uzbek - Cyrilic": "uzb_cyrl",
    "Uzbek": "uzb",
    "Vietnamese (Script)": "Vietnamese",
    "Vietnamese": "vie",
    "Welsh": "cym",
    "West Frisian": "fry",
    "Yiddish": "yid",
    "Yoruba": "yor",
}


def find_pdfs_in_directory(directory: str) -> list[str]:
    """Walk a directory and return all PDF file paths."""
    pdfs = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(".pdf"):
                pdfs.append(os.path.join(dirpath, filename))
    return pdfs


def prepare_output_directory(input_dir: str, output_dir: str) -> str:
    """Create MDMT-OCR-Output directory mirroring input folder structure (dirs only).

    Returns the path to the created output directory.
    """
    output_path = os.path.join(output_dir, "MDMT-OCR-Output")
    if os.path.exists(output_path) and os.path.isdir(output_path):
        shutil.rmtree(output_path)

    def ignore_files(directory, files):
        return [f for f in files if os.path.isfile(os.path.join(directory, f))]

    shutil.copytree(input_dir, output_path, ignore=ignore_files)
    return output_path


def build_ocr_params(
    language_codes: list[str],
    deskew: bool,
    rotate_pages: bool,
    rotate_threshold: int,
    redo_ocr: bool,
    output_type: str,
    sidecar_path: str | None,
) -> dict:
    """Build the kwargs dict for ocrmypdf.ocr().

    Note: deskew and redo_ocr are mutually exclusive in ocrmypdf.
    If both are True, redo_ocr takes precedence and deskew is set to False.
    """
    if redo_ocr and deskew:
        deskew = False
    params = {
        "language": "+".join(language_codes),
        "redo_ocr": redo_ocr,
        "skip_text": not redo_ocr,
        "deskew": deskew,
        "rotate_pages": rotate_pages,
        "output_type": output_type,
        "invalidate_digital_signatures": True,
    }
    if rotate_pages:
        params["rotate_pages_threshold"] = rotate_threshold
    if sidecar_path:
        params["sidecar"] = sidecar_path
    return params


def ocr_single_file(
    input_path: str,
    output_path: str,
    tessdata_dir: str,
    ocr_params: dict,
) -> dict:
    """Run OCR on a single PDF. Returns a result dict with status and message."""
    try:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        tessconfig = os.path.join(tessdata_dir, "tessconfigs")
        ocrmypdf.configure_logging(verbosity=ocrmypdf.Verbosity.default)
        # Only pass tesseract_config if the tessconfigs directory exists
        if os.path.isdir(tessconfig):
            ocr_params["tesseract_config"] = tessconfig
        ocrmypdf.ocr(
            input_path,
            output_path,
            **ocr_params,
        )
        return {"status": "success", "input": input_path, "output": output_path}
    except Exception as e:
        return {"status": "error", "input": input_path, "message": str(e)}


def run_ocr_batch(
    input_dir: str,
    output_dir: str,
    tessdata_dir: str,
    language_names: list[str],
    deskew: bool = False,
    rotate_pages: bool = False,
    rotate_threshold: int = 15,
    redo_ocr: bool = False,
    output_type: str = "pdf",
    extract_text: bool = False,
    on_progress=None,
) -> list[dict]:
    """Run OCR on all PDFs in input_dir. Returns list of result dicts.

    Args:
        on_progress: Optional callback(current, total, filename) for progress updates.
    """
    language_codes = [TESSERACT_LANGUAGES[name] for name in language_names]
    pdfs = find_pdfs_in_directory(input_dir)
    if not pdfs:
        return []

    output_root = prepare_output_directory(input_dir, output_dir)
    results = []

    for i, pdf_path in enumerate(pdfs):
        rel_path = os.path.relpath(pdf_path, input_dir)
        out_path = os.path.join(output_root, rel_path)
        sidecar = os.path.splitext(out_path)[0] + ".txt" if extract_text else None

        ocr_params = build_ocr_params(
            language_codes=language_codes,
            deskew=deskew,
            rotate_pages=rotate_pages,
            rotate_threshold=rotate_threshold,
            redo_ocr=redo_ocr,
            output_type=output_type,
            sidecar_path=sidecar,
        )

        if on_progress:
            on_progress(i, len(pdfs), os.path.basename(pdf_path))

        result = ocr_single_file(pdf_path, out_path, tessdata_dir, ocr_params)
        results.append(result)

    if on_progress:
        on_progress(len(pdfs), len(pdfs), "Done")

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_ocr_logic.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add OCR/__init__.py OCR/ocr_logic.py tests/test_ocr_logic.py
git commit -m "feat: extract OCR business logic from ocrWindow into OCR/ocr_logic.py"
```

---

### Task 5: Extract Audio Transcription business logic

**Files:**
- Create: `Audio_Transcription/transcription_logic.py`
- Create: `Audio_Transcription/__init__.py`
- Create: `tests/test_transcription_logic.py`

- [ ] **Step 1: Write tests for transcription logic**

Create `tests/test_transcription_logic.py`:

```python
import os
import pytest
from Audio_Transcription.transcription_logic import (
    AUDIO_FORMATS,
    find_audio_files,
)


def test_audio_formats_is_tuple():
    assert isinstance(AUDIO_FORMATS, tuple)
    assert ".mp3" in AUDIO_FORMATS
    assert ".wav" in AUDIO_FORMATS


def test_find_audio_files(tmp_path):
    (tmp_path / "song.mp3").write_text("fake")
    (tmp_path / "clip.wav").write_text("fake")
    (tmp_path / "readme.txt").write_text("not audio")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "talk.m4a").write_text("fake")

    files = find_audio_files(str(tmp_path))
    assert len(files) == 3
    assert all(
        f.endswith(AUDIO_FORMATS) for f in files
    )


def test_find_audio_files_empty(tmp_path):
    files = find_audio_files(str(tmp_path))
    assert files == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_transcription_logic.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement transcription logic module**

Create `Audio_Transcription/__init__.py` (empty) and `Audio_Transcription/transcription_logic.py`:

```python
"""Audio transcription business logic extracted from audioTranscriptionWindow.py."""
import os

AUDIO_FORMATS = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")


def find_audio_files(directory: str) -> list[str]:
    """Walk a directory and return all audio file paths."""
    audio_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(AUDIO_FORMATS):
                audio_files.append(os.path.join(dirpath, filename))
    return audio_files


def transcribe_file(model, audio_path: str, output_path: str = None) -> dict:
    """Transcribe a single audio file using a loaded Whisper model.

    Args:
        model: A loaded whisper model instance.
        audio_path: Path to the audio file.
        output_path: Optional output .txt path. If None, uses audio_path + '.txt'.

    Returns:
        Dict with 'status', 'input', 'output', and optionally 'text' or 'message'.
    """
    if output_path is None:
        output_path = audio_path + ".txt"
    try:
        result = model.transcribe(audio_path)
        with open(output_path, "w") as f:
            f.write(result["text"])
        return {
            "status": "success",
            "input": audio_path,
            "output": output_path,
            "text": result["text"],
        }
    except Exception as e:
        return {"status": "error", "input": audio_path, "message": str(e)}


def transcribe_directory(
    directory: str,
    model_name: str = "tiny",
    download_root: str = None,
    on_progress=None,
) -> list[dict]:
    """Transcribe all audio files in a directory.

    Args:
        directory: Input directory to scan for audio files.
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium').
        download_root: Custom download directory for Whisper models.
            Callers MUST pass get_whisper_models_dir() to keep models
            in the app data directory per the spec. If None, Whisper
            downloads to ~/.cache/whisper/ which bypasses our asset management.
        on_progress: Optional callback(current, total, filename).

    Returns:
        List of result dicts.
    """
    import whisper

    audio_files = find_audio_files(directory)
    if not audio_files:
        return []

    model = whisper.load_model(model_name, download_root=download_root)
    results = []

    for i, audio_path in enumerate(audio_files):
        if on_progress:
            on_progress(i, len(audio_files), os.path.basename(audio_path))

        result = transcribe_file(model, audio_path)
        results.append(result)

    if on_progress:
        on_progress(len(audio_files), len(audio_files), "Done")

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_transcription_logic.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add Audio_Transcription/__init__.py Audio_Transcription/transcription_logic.py tests/test_transcription_logic.py
git commit -m "feat: extract audio transcription logic from audioTranscriptionWindow"
```

---

### Task 6: Extend Translation module with LANGUAGE_CODES

**Files:**
- Modify: `Translation/googletranslateWrapper.py`
- Create: `Translation/__init__.py`
- Create: `tests/test_translation_wrapper.py`

Note: `Translation/__init__.py` must be created for the module to be importable as a package. The existing code worked around this with `sys.path.append()`, but proper packaging requires `__init__.py`.

Note: The file-handling orchestration (reading files, chunking, calling Google Translate) already exists in `translate_documents_async()`. The only extraction needed is moving `LANGUAGE_CODES` from `translationWindow.py` into the wrapper module.

- [ ] **Step 1: Write tests for LANGUAGE_CODES**

Create `tests/test_translation_wrapper.py`:

```python
from Translation.googletranslateWrapper import LANGUAGE_CODES


def test_language_codes_contains_english():
    assert "English" in LANGUAGE_CODES
    assert LANGUAGE_CODES["English"] == "en"


def test_language_codes_contains_spanish():
    assert "Spanish" in LANGUAGE_CODES
    assert LANGUAGE_CODES["Spanish"] == "es"


def test_language_codes_has_entries():
    assert len(LANGUAGE_CODES) >= 14
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_translation_wrapper.py -v`
Expected: FAIL — `LANGUAGE_CODES` not defined in the module.

- [ ] **Step 3: Add LANGUAGE_CODES to googletranslateWrapper.py**

Add at the top of `Translation/googletranslateWrapper.py`, after the existing imports and before the `DEFAULT_*` constants:

```python
# Language display names to Google Translate codes
LANGUAGE_CODES = {
    "Arabic": "ar",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Portuguese": "pt",
    "Russian": "ru",
    "Chinese Simplified": "zh-CN",
    "Chinese Traditional": "zh-TW",
    "Dutch": "nl",
    "Hindi": "hi",
    "Swedish": "sv",
    "English": "en",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_translation_wrapper.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add Translation/__init__.py Translation/googletranslateWrapper.py tests/test_translation_wrapper.py
git commit -m "feat: add LANGUAGE_CODES dict to translation wrapper module"
```

---

### Task 6b: Decouple advancedKeywordSearchLogic from aksWindow

**Files:**
- Modify: `Advanced_Keyword_Search/advancedKeywordSearchLogic.py`

**Problem:** `core_logic()` imports `logic_error` and `logic_message` from `aksWindow.py` (tkinter messagebox wrappers). Since `aksWindow.py` will be deleted, this circular dependency must be broken.

**Solution:** Replace the direct imports with callback parameters that default to `print`. This keeps the backend logic fully independent of any UI framework.

- [ ] **Step 1: Modify core_logic to accept callbacks**

In `Advanced_Keyword_Search/advancedKeywordSearchLogic.py`, replace:

```python
    from aksWindow import logic_error
    from aksWindow import logic_message
```

with:

```python
    # Use callbacks passed from the caller (defaults set in function signature)
```

And change the `core_logic` function signature from:

```python
def core_logic(contextLength, basicFilterState, PDFDirectory, outputDirectory,
               keywordFilePath, manualKeywords, filterFilePath, manualFilters):
```

to:

```python
def core_logic(contextLength, basicFilterState, PDFDirectory, outputDirectory,
               keywordFilePath, manualKeywords, filterFilePath, manualFilters,
               on_error=None, on_message=None):
```

At the top of the function body, add:

```python
    logic_error = on_error or print
    logic_message = on_message or print
```

This preserves all existing calls to `logic_error(...)` and `logic_message(...)` throughout the function without changing them.

- [ ] **Step 2: Verify existing tests still work (if any), and test import**

Run: `source .venv/bin/activate && python -c "from Advanced_Keyword_Search.advancedKeywordSearchLogic import core_logic; print('OK')"`
Expected: "OK" (no import of aksWindow)

- [ ] **Step 3: Commit**

```bash
git add Advanced_Keyword_Search/advancedKeywordSearchLogic.py
git commit -m "refactor: decouple core_logic from aksWindow UI callbacks"
```

---

## Chunk 3: App Shell

### Task 7: Create app.py with sidebar navigation and page routing

**Files:**
- Create: `app.py`
- Create: `pages/__init__.py`
- Create: `pages/welcome.py`
- Create: `pages/about.py`

- [ ] **Step 1: Create pages/__init__.py**

Create `pages/__init__.py` (empty file).

- [ ] **Step 2: Create welcome page**

Create `pages/welcome.py`:

```python
"""Welcome / first-run page."""
from nicegui import ui
from config import AppConfig


def welcome_page():
    config = AppConfig()

    ui.label("Welcome to MDMT").classes("text-h3")
    ui.label("Modular Digital Methodologies Toolkit").classes("text-subtitle1")

    ui.separator()

    with ui.card().classes("w-full"):
        ui.label("Getting Started").classes("text-h5")
        ui.markdown("""
MDMT provides tools for digital humanities research:

- **Document Processing** — OCR, Audio Transcription, Translation
- **Text Analysis** — Keyword Search, Named Entity Recognition, Relationship Extraction, Co-Word Analysis
- **AI** — RAG Chatbot for querying your documents

Use the sidebar to navigate to any module. Some modules require downloading
models or language data first — visit the **Downloads** page to manage these.
        """)

    with ui.card().classes("w-full mt-4"):
        ui.label("Optional Downloads").classes("text-h5")
        ui.markdown("""
Some features require additional data to be downloaded:

- **OCR**: Tesseract language files (~12-15 MB each)
- **Audio Transcription**: Whisper models (75 MB - 1.5 GB)
- **RAG Chat**: Llama LLM model (~2.3 GB)

You can download these from the **Downloads** page, or they will prompt you when needed.
        """)
        ui.button("Go to Downloads", on_click=lambda: ui.navigate.to("/downloads")).props("outline")
```

- [ ] **Step 3: Create about page**

Create `pages/about.py`:

```python
"""Help / About / License page."""
from nicegui import ui


def about_page():
    ui.label("About MDMT").classes("text-h4")
    ui.separator()

    with ui.card().classes("w-full"):
        ui.label("Modular Digital Methodologies Toolkit").classes("text-h5")
        ui.markdown("""
**Author:** James C. Caldwell

MDMT is a modular application for digital humanities and research workflows,
providing tools for text analysis, document processing, and data extraction.
        """)

    with ui.expansion("Help", icon="help").classes("w-full mt-4"):
        ui.markdown("""
**Getting Started:**
1. Use the sidebar to navigate between modules
2. Each module has its own input/output configuration
3. Visit the Downloads page to manage models and language data

**Modules:**
- **OCR**: Convert image-based PDFs to searchable text using Tesseract
- **Audio Transcription**: Convert speech to text using OpenAI Whisper
- **Translation**: Translate documents using Google Translate
- **Advanced Keywords**: Batch keyword analysis across PDF collections
- **NER**: Named Entity Recognition using HuggingFace BERT
- **Relationship Extraction**: Discover entity connections with network graphs
- **Co-Word Analysis**: Generate word co-occurrence networks
- **RAG Chat**: Chat with your documents using Llama AI
        """)

    with ui.expansion("License", icon="gavel").classes("w-full mt-2"):
        ui.markdown("See project LICENSE file for full license terms.")
```

- [ ] **Step 4: Create app.py with sidebar and routing**

Create `app.py`:

```python
"""MDMT main application entry point with NiceGUI sidebar navigation."""
import os
from nicegui import ui, app
from config import AppConfig, get_app_data_dir, get_nltk_data_dir


def create_sidebar():
    """Build the persistent sidebar navigation."""
    with ui.left_drawer(value=True).classes("bg-blue-grey-1") as drawer:
        ui.label("MDMT").classes("text-h5 q-mb-md")

        ui.label("Document Processing").classes("text-overline q-mt-md")
        ui.button("OCR", on_click=lambda: ui.navigate.to("/ocr"), icon="document_scanner").props("flat align=left").classes("w-full")
        ui.button("Audio Transcription", on_click=lambda: ui.navigate.to("/audio"), icon="mic").props("flat align=left").classes("w-full")
        ui.button("Translation", on_click=lambda: ui.navigate.to("/translation"), icon="translate").props("flat align=left").classes("w-full")

        ui.label("Analysis").classes("text-overline q-mt-lg")
        ui.button("Advanced Keywords", on_click=lambda: ui.navigate.to("/keywords"), icon="search").props("flat align=left").classes("w-full")
        ui.button("NER", on_click=lambda: ui.navigate.to("/ner"), icon="person_search").props("flat align=left").classes("w-full")
        ui.button("Relationships", on_click=lambda: ui.navigate.to("/relationships"), icon="hub").props("flat align=left").classes("w-full")
        ui.button("Co-Words", on_click=lambda: ui.navigate.to("/cowords"), icon="grain").props("flat align=left").classes("w-full")

        ui.label("AI").classes("text-overline q-mt-lg")
        ui.button("RAG Chat", on_click=lambda: ui.navigate.to("/rag"), icon="smart_toy").props("flat align=left").classes("w-full")

        ui.separator().classes("q-mt-lg")
        ui.button("Downloads", on_click=lambda: ui.navigate.to("/downloads"), icon="download").props("flat align=left").classes("w-full")
        ui.button("Help / About", on_click=lambda: ui.navigate.to("/about"), icon="info").props("flat align=left").classes("w-full")

    return drawer


@ui.page("/")
def index():
    config = AppConfig()
    if config.exists():
        last_page = config.get("last_page", "/welcome")
        ui.navigate.to(last_page)
    else:
        ui.navigate.to("/welcome")


@ui.page("/welcome")
def welcome():
    create_sidebar()
    from pages.welcome import welcome_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        welcome_page()


@ui.page("/about")
def about():
    create_sidebar()
    from pages.about import about_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        about_page()


# Placeholder pages for modules not yet migrated
def _placeholder_page(name: str):
    def page_fn():
        create_sidebar()
        with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
            ui.label(f"{name}").classes("text-h4")
            ui.label("This module is not yet migrated to the web UI.").classes("text-subtitle1")
    return page_fn


for route, name in [
    ("/ocr", "OCR"),
    ("/audio", "Audio Transcription"),
    ("/translation", "Translation"),
    ("/keywords", "Advanced Keywords"),
    ("/ner", "NER"),
    ("/relationships", "Relationship Extraction"),
    ("/cowords", "Co-Word Analysis"),
    ("/rag", "RAG Chat"),
    ("/downloads", "Downloads"),
]:
    ui.page(route)(_placeholder_page(name))


def main():
    """Initialize app data directory and start NiceGUI."""
    get_app_data_dir()

    # Point NLTK to our managed data directory
    import nltk
    nltk_dir = get_nltk_data_dir()
    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)

    ui.run(
        native=True,
        title="MDMT - Modular Digital Methodologies Toolkit",
        window_size=(1200, 800),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
```

- [ ] **Step 5: Run the app shell and manually verify**

Run: `source .venv/bin/activate && python app.py`

Verify:
1. Native window opens with the Welcome page
2. Sidebar shows all module categories and buttons
3. Clicking sidebar buttons navigates to placeholder pages
4. About page renders correctly

- [ ] **Step 6: Commit**

```bash
git add app.py pages/__init__.py pages/welcome.py pages/about.py
git commit -m "feat: add app shell with sidebar navigation and page routing"
```

---

### Task 8: Create Downloads page

**Files:**
- Create: `pages/downloads.py`

- [ ] **Step 1: Implement downloads page**

Create `pages/downloads.py`:

```python
"""Asset manager / downloads page."""
import os
from nicegui import ui, run
from config import get_tessdata_dir, get_models_dir, get_whisper_models_dir, get_nltk_data_dir


# Known Tesseract language files available for download
TESSDATA_LANGUAGES = {
    "English": "eng",
    "French": "fra",
    "German": "deu",
    "Spanish": "spa",
    "Italian": "ita",
    "Portuguese": "por",
    "Russian": "rus",
    "Chinese Simplified": "chi_sim",
    "Chinese Traditional": "chi_tra",
    "Japanese": "jpn",
    "Korean": "kor",
    "Arabic": "ara",
    "Hindi": "hin",
    "Dutch": "nld",
    "Swedish": "swe",
}

TESSDATA_GITHUB_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"

WHISPER_MODELS = {
    "tiny": "~75 MB",
    "base": "~142 MB",
    "small": "~466 MB",
    "medium": "~1.5 GB",
}


def _is_tessdata_installed(lang_code: str) -> bool:
    return os.path.exists(os.path.join(get_tessdata_dir(), f"{lang_code}.traineddata"))


def _is_whisper_installed(model_name: str) -> bool:
    model_dir = get_whisper_models_dir()
    return os.path.exists(os.path.join(model_dir, f"{model_name}.pt"))


async def _download_tessdata(lang_code: str, status_label: ui.label):
    """Download a single Tesseract language file."""
    import urllib.request

    url = f"{TESSDATA_GITHUB_URL}/{lang_code}.traineddata"
    dest = os.path.join(get_tessdata_dir(), f"{lang_code}.traineddata")
    status_label.set_text(f"Downloading {lang_code}...")

    def do_download():
        urllib.request.urlretrieve(url, dest)

    await run.io_bound(do_download)
    status_label.set_text(f"{lang_code} installed")


async def _download_whisper_model(model_name: str, status_label: ui.label):
    """Download a Whisper model via the whisper library."""
    status_label.set_text(f"Downloading {model_name}...")

    def do_download():
        import whisper
        whisper.load_model(model_name, download_root=get_whisper_models_dir())

    await run.io_bound(do_download)
    status_label.set_text(f"{model_name} installed")


def downloads_page():
    ui.label("Downloads & Models").classes("text-h4")
    ui.label("Manage optional assets. Downloads come from official sources.").classes("text-subtitle1")
    ui.separator()

    # Tesseract Languages
    with ui.card().classes("w-full"):
        ui.label("OCR Languages (Tesseract)").classes("text-h5")
        ui.label(f"Install location: {get_tessdata_dir()}").classes("text-caption")

        for display_name, lang_code in TESSDATA_LANGUAGES.items():
            installed = _is_tessdata_installed(lang_code)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{display_name} ({lang_code})").classes("w-48")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )
                if not installed:
                    ui.button(
                        "Download",
                        on_click=lambda lc=lang_code, sl=status: _download_tessdata(lc, sl),
                    ).props("flat dense")

    # Whisper Models
    with ui.card().classes("w-full mt-4"):
        ui.label("Whisper Models (Audio Transcription)").classes("text-h5")
        ui.label(f"Install location: {get_whisper_models_dir()}").classes("text-caption")

        for model_name, size in WHISPER_MODELS.items():
            installed = _is_whisper_installed(model_name)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{model_name} ({size})").classes("w-48")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )
                if not installed:
                    ui.button(
                        "Download",
                        on_click=lambda mn=model_name, sl=status: _download_whisper_model(mn, sl),
                    ).props("flat dense")

    # NLTK Data
    with ui.card().classes("w-full mt-4"):
        ui.label("NLTK Data (NER, Co-Word Analysis)").classes("text-h5")
        ui.label(f"Install location: {get_nltk_data_dir()}").classes("text-caption")

        nltk_packages = {
            "punkt_tab": "Sentence tokenizer",
            "averaged_perceptron_tagger_eng": "POS tagger",
            "maxent_ne_chunker_tab": "Named entity chunker",
            "words": "English word list",
            "stopwords": "Stop words",
        }

        for pkg_name, description in nltk_packages.items():
            pkg_dir = os.path.join(get_nltk_data_dir(), "tokenizers" if "punkt" in pkg_name else "taggers" if "tagger" in pkg_name else "chunkers" if "chunker" in pkg_name else "corpora", pkg_name)
            installed = os.path.exists(pkg_dir)
            with ui.row().classes("items-center w-full"):
                ui.label(f"{description} ({pkg_name})").classes("w-64")
                status = ui.label("Installed" if installed else "Not installed").classes(
                    "text-positive" if installed else "text-grey"
                )

        async def download_all_nltk(status_label):
            status_label.set_text("Downloading NLTK data...")

            def do_download():
                import nltk
                nltk_dir = get_nltk_data_dir()
                for pkg in nltk_packages:
                    nltk.download(pkg, download_dir=nltk_dir, quiet=True)

            await run.io_bound(do_download)
            status_label.set_text("All NLTK data installed")

        nltk_status = ui.label("")
        ui.button("Download All NLTK Data", on_click=lambda: download_all_nltk(nltk_status)).props("flat")

    # LLM Models
    with ui.card().classes("w-full mt-4"):
        ui.label("LLM Models (RAG Chat)").classes("text-h5")
        ui.label(f"Install location: {get_models_dir()}").classes("text-caption")

        models_dir = get_models_dir()
        gguf_files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")] if os.path.exists(models_dir) else []

        if gguf_files:
            for f in gguf_files:
                size_mb = os.path.getsize(os.path.join(models_dir, f)) / (1024 * 1024)
                ui.label(f"{f} ({size_mb:.0f} MB) - Installed").classes("text-positive")
        else:
            ui.markdown("""
No LLM models found. To add a model:

1. Download a GGUF model from [HuggingFace](https://huggingface.co)
2. Place it in the models directory shown above

Recommended: `Llama-3.2-3B-Instruct-Q5_K_M.gguf` (~2.3 GB)
            """)
```

- [ ] **Step 2: Wire downloads page into app.py**

In `app.py`, replace the `/downloads` placeholder registration in the loop. Remove `"/downloads"` from the placeholder loop list and add a proper route:

```python
@ui.page("/downloads")
def downloads():
    create_sidebar()
    from pages.downloads import downloads_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        downloads_page()
```

- [ ] **Step 3: Run and manually verify**

Run: `source .venv/bin/activate && python app.py`

Verify:
1. Navigate to Downloads via sidebar
2. Tesseract languages show installed/not-installed status
3. Download buttons appear for missing assets

- [ ] **Step 4: Commit**

```bash
git add pages/downloads.py app.py
git commit -m "feat: add Downloads page for managing Tesseract, Whisper, and LLM assets"
```

---

## Chunk 4: Module Migration — Document Processing

### Task 9: OCR page

**Files:**
- Create: `pages/ocr.py`
- Modify: `app.py` (wire route)

- [ ] **Step 1: Implement OCR page**

Create `pages/ocr.py`:

```python
"""OCR processing page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig, get_tessdata_dir
from OCR.ocr_logic import TESSERACT_LANGUAGES, run_ocr_batch


def _find_tessdata_dir() -> str:
    """Check app data dir first, then fall back to bundled OCR/tessdata/."""
    app_tessdata = get_tessdata_dir()
    bundled_tessdata = os.path.join(os.path.dirname(os.path.dirname(__file__)), "OCR", "tessdata")

    # Prefer app data dir if it has any .traineddata files
    if os.path.isdir(app_tessdata) and any(f.endswith(".traineddata") for f in os.listdir(app_tessdata)):
        return app_tessdata
    # Fall back to bundled tessdata
    if os.path.isdir(bundled_tessdata):
        return bundled_tessdata
    return app_tessdata


def ocr_page():
    config = AppConfig()
    tessdata_dir = _find_tessdata_dir()

    # Filter languages to only those with installed tessdata
    available_langs = {
        name: code for name, code in TESSERACT_LANGUAGES.items()
        if os.path.exists(os.path.join(tessdata_dir, f"{code}.traineddata"))
    }

    if not available_langs:
        with ui.card().classes("w-full"):
            ui.label("No OCR languages installed").classes("text-h5 text-negative")
            ui.label("Please download at least one language from the Downloads page.")
            ui.button("Go to Downloads", on_click=lambda: ui.navigate.to("/downloads")).props("outline")
        return

    ui.label("OCR Processing").classes("text-h4")
    ui.separator()

    # Input directory
    input_dir = ui.input(
        "Input Directory",
        value=config.get("defaults.ocr_input_dir", ""),
    ).classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    # Output directory
    output_dir = ui.input(
        "Output Directory",
        value=config.get("defaults.ocr_output_dir", ""),
    ).classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(output_dir), icon="folder_open").props("flat")

    # Language selection
    lang_select = ui.select(
        list(available_langs.keys()),
        multiple=True,
        label="Languages",
        value=["English"] if "English" in available_langs else [],
    ).classes("w-full")

    # Options
    with ui.row().classes("w-full"):
        deskew = ui.checkbox("Deskew", value=False)
        rotate = ui.checkbox("Rotate Pages", value=False)
        redo_ocr = ui.checkbox("Redo OCR", value=False)
        pdfa = ui.checkbox("PDF/A Output", value=False)
        extract_text = ui.checkbox("Extract Text", value=False)

    # Rotation threshold (visible only when rotate is checked)
    with ui.row().classes("w-full").bind_visibility_from(rotate, "value"):
        ui.label("Rotation Confidence:")
        rotate_threshold = ui.radio(
            {2: "Low", 15: "Normal", 30: "High"},
            value=15,
        ).props("inline")

    ui.separator()

    # Run button
    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")
    results_table = ui.column().classes("w-full")

    async def run_ocr():
        in_dir = input_dir.value
        out_dir = output_dir.value

        if not in_dir or not out_dir:
            ui.notify("Please select both input and output directories.", type="warning")
            return
        if in_dir == out_dir:
            ui.notify("Input and output directories cannot be the same.", type="warning")
            return
        if not lang_select.value:
            ui.notify("Please select at least one language.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Processing...")
        results_table.clear()

        def do_ocr():
            return run_ocr_batch(
                input_dir=in_dir,
                output_dir=out_dir,
                tessdata_dir=tessdata_dir,
                language_names=lang_select.value,
                deskew=deskew.value,
                rotate_pages=rotate.value,
                rotate_threshold=rotate_threshold.value,
                redo_ocr=redo_ocr.value,
                output_type="pdfa" if pdfa.value else "pdf",
                extract_text=extract_text.value,
            )

        results = await run.io_bound(do_ocr)
        progress.set_visibility(False)

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        status_label.set_text(f"Complete: {success_count} succeeded, {error_count} failed")

        with results_table:
            for r in results:
                icon = "check_circle" if r["status"] == "success" else "error"
                color = "text-positive" if r["status"] == "success" else "text-negative"
                msg = os.path.basename(r["input"])
                if r["status"] == "error":
                    msg += f" — {r.get('message', 'Unknown error')}"
                with ui.row().classes("items-center"):
                    ui.icon(icon).classes(color)
                    ui.label(msg)

        # Save defaults
        config.set("defaults.ocr_input_dir", in_dir)
        config.set("defaults.ocr_output_dir", out_dir)
        config.set("last_page", "/ocr")
        config.save()

    ui.button("Run OCR", on_click=run_ocr, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    """Open native directory picker and set the input value."""
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire OCR page into app.py**

Remove `"/ocr"` from the placeholder loop. Add proper route:

```python
@ui.page("/ocr")
def ocr():
    create_sidebar()
    from pages.ocr import ocr_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ocr_page()
```

- [ ] **Step 3: Run and manually verify**

Run: `source .venv/bin/activate && python app.py`
Navigate to OCR. Verify: language dropdown populates from installed tessdata, browse buttons open native dialogs, options toggle correctly.

- [ ] **Step 4: Commit**

```bash
git add pages/ocr.py app.py
git commit -m "feat: add OCR page with NiceGUI"
```

---

### Task 10: Audio Transcription page

**Files:**
- Create: `pages/audio.py`
- Modify: `app.py` (wire route)

- [ ] **Step 1: Implement Audio page**

Create `pages/audio.py`:

```python
"""Audio transcription page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig, get_whisper_models_dir
from Audio_Transcription.transcription_logic import transcribe_directory


def audio_page():
    config = AppConfig()

    ui.label("Audio Transcription").classes("text-h4")
    ui.label("Convert speech in audio files to text using OpenAI Whisper").classes("text-subtitle1")
    ui.separator()

    # Input directory
    input_dir = ui.input("Audio Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    # Model selection
    model_select = ui.select(
        ["tiny", "base", "small", "medium"],
        label="Whisper Model",
        value=config.get("defaults.whisper_model", "tiny"),
    ).classes("w-48")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")
    results_area = ui.column().classes("w-full")

    async def run_transcription():
        audio_dir = input_dir.value
        if not audio_dir:
            ui.notify("Please select an audio directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Loading model and transcribing...")
        results_area.clear()

        def do_transcribe():
            return transcribe_directory(
                directory=audio_dir,
                model_name=model_select.value,
                download_root=get_whisper_models_dir(),
            )

        results = await run.io_bound(do_transcribe)
        progress.set_visibility(False)

        if not results:
            status_label.set_text("No audio files found in the selected directory.")
            return

        success_count = sum(1 for r in results if r["status"] == "success")
        status_label.set_text(f"Complete: {success_count}/{len(results)} files transcribed")

        with results_area:
            for r in results:
                with ui.card().classes("w-full"):
                    icon = "check_circle" if r["status"] == "success" else "error"
                    color = "text-positive" if r["status"] == "success" else "text-negative"
                    with ui.row().classes("items-center"):
                        ui.icon(icon).classes(color)
                        ui.label(os.path.basename(r["input"]))
                    if r["status"] == "success" and r.get("text"):
                        preview = r["text"][:500] + ("..." if len(r["text"]) > 500 else "")
                        with ui.expansion("Preview transcript"):
                            ui.label(preview).classes("font-mono text-sm")

        config.set("defaults.whisper_model", model_select.value)
        config.set("last_page", "/audio")
        config.save()

    ui.button("Transcribe", on_click=run_transcription, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route in app.py**

Remove `"/audio"` from placeholder loop, add proper route:

```python
@ui.page("/audio")
def audio():
    create_sidebar()
    from pages.audio import audio_page
    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        audio_page()
```

- [ ] **Step 3: Commit**

```bash
git add pages/audio.py app.py
git commit -m "feat: add Audio Transcription page with NiceGUI"
```

---

### Task 11: Translation page

**Files:**
- Create: `pages/translation.py`
- Modify: `app.py` (wire route)

- [ ] **Step 1: Implement Translation page**

Create `pages/translation.py`:

```python
"""Translation page."""
import os
import asyncio
from nicegui import ui, run
import webview
from config import AppConfig
from Translation.googletranslateWrapper import LANGUAGE_CODES, translate_documents_async


def translation_page():
    config = AppConfig()

    ui.label("Translation").classes("text-h4")
    ui.label("Translate documents using Google Translate").classes("text-subtitle1")
    ui.separator()

    # Input directory
    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    # Target language
    target_lang = ui.select(
        list(LANGUAGE_CODES.keys()),
        label="Target Language",
        value=config.get("defaults.translation_target_lang_display", "Spanish"),
    ).classes("w-64")

    # Output suffix
    suffix = ui.input("Output Suffix", value="_translated").classes("w-64")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_translation():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        lang_code = LANGUAGE_CODES.get(target_lang.value, "en")
        progress.set_visibility(True)
        status_label.set_text(f"Translating to {target_lang.value}...")

        settings = {
            "TARGET_LANG": lang_code,
            "SUFFIX": suffix.value or "_translated",
            "DIRECTORY": in_dir,
            "MAX_CHARS": 5000,
        }

        def do_translate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(translate_documents_async(settings))
            loop.close()

        try:
            await run.io_bound(do_translate)
            status_label.set_text("Translation completed successfully!")
            ui.notify("Translation complete!", type="positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Translation error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("defaults.translation_target_lang_display", target_lang.value)
        config.set("last_page", "/translation")
        config.save()

    ui.button("Translate", on_click=run_translation, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route in app.py**

Remove `"/translation"` from placeholder loop, add proper route.

- [ ] **Step 3: Commit**

```bash
git add pages/translation.py app.py
git commit -m "feat: add Translation page with NiceGUI"
```

---

## Chunk 5: Module Migration — Analysis & AI

**Note on UX improvements:** The spec describes inline results tables, in-app charts, copy/download buttons, and drag-and-drop for several modules. This initial migration focuses on functional parity — all modules work with the same backend logic, using directory/file selectors and progress feedback. The following UX enhancements are deferred to a follow-up iteration:
- Inline results tables and CSV download buttons (Keywords, NER, Relationships, Co-Words)
- In-app matplotlib/plotly chart rendering (Keywords, Co-Words)
- Copy/download buttons for transcripts (Audio)
- Inline translation preview (Translation)

These can be added incrementally once the basic migration is complete and tested.

### Task 12: Advanced Keyword Search page

**Files:**
- Create: `pages/keywords.py`
- Modify: `app.py`

- [ ] **Step 1: Implement Keywords page**

Create `pages/keywords.py`:

```python
"""Advanced keyword search page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig
from Advanced_Keyword_Search.advancedKeywordSearchLogic import core_logic


def keywords_page():
    config = AppConfig()

    ui.label("Advanced Keyword Search").classes("text-h4")
    ui.label("Batch keyword analysis across PDF collections").classes("text-subtitle1")
    ui.separator()

    # Input/output directories
    pdf_dir = ui.input("PDF Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(pdf_dir), icon="folder_open").props("flat")

    output_dir = ui.input("Output Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(output_dir), icon="folder_open").props("flat")

    # Context length
    context_length = ui.number("Context Length (words)", value=5, min=1, max=50).classes("w-48")

    # Keywords
    ui.label("Keywords (one per line)").classes("text-subtitle2 q-mt-md")
    keywords_text = ui.textarea(placeholder="Enter keywords, one per line...").classes("w-full")

    # Filters
    with ui.row().classes("items-center"):
        basic_filter = ui.checkbox("Basic Filter (letters & numbers only)", value=False)
    filters_text = ui.textarea(placeholder="Enter filter words, one per line...").classes("w-full")
    filters_text.bind_enabled_from(basic_filter, "value", backward=lambda v: not v)

    # Optional: keyword/filter file paths
    with ui.expansion("Or load from files...").classes("w-full"):
        keyword_file = ui.input("Keyword File Path").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(keyword_file), icon="folder_open").props("flat")
        filter_file = ui.input("Filter File Path").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(filter_file), icon="folder_open").props("flat")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_analysis():
        in_dir = pdf_dir.value
        out_dir = output_dir.value

        if not in_dir or not out_dir:
            ui.notify("Please select both input and output directories.", type="warning")
            return
        if in_dir == out_dir:
            ui.notify("Input and output directories cannot be the same.", type="warning")
            return

        manual_kw = keywords_text.value or ""
        manual_fl = filters_text.value or ""
        kw_file = keyword_file.value or ""
        fl_file = filter_file.value or ""

        if not manual_kw and not kw_file:
            ui.notify("Please enter keywords or select a keyword file.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Analyzing...")

        def do_analysis():
            core_logic(
                str(int(context_length.value)),
                1 if basic_filter.value else 0,
                in_dir,
                out_dir,
                kw_file,
                manual_kw,
                fl_file,
                manual_fl,
            )

        try:
            await run.io_bound(do_analysis)
            status_label.set_text("Analysis complete!")
            ui.notify("Keyword analysis complete! Check the output directory.", type="positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Analysis error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/keywords")
        config.save()

    ui.button("Analyze", on_click=run_analysis, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])


def _browse_file(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route in app.py, commit**

```bash
git add pages/keywords.py app.py
git commit -m "feat: add Advanced Keyword Search page with NiceGUI"
```

---

### Task 13: NER page

**Files:**
- Create: `pages/ner.py`
- Modify: `app.py`

- [ ] **Step 1: Implement NER page**

Create `pages/ner.py`:

```python
"""Named Entity Recognition page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig
from NLP.named_entity_recognition import main as ner_main


def ner_page():
    config = AppConfig()

    ui.label("Named Entity Recognition").classes("text-h4")
    ui.label("Identify people, organizations, locations, and other entities in documents").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_ner():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Running NER analysis...")

        try:
            await run.io_bound(ner_main, in_dir)
            status_label.set_text("NER analysis complete! Results saved in input directory.")
            ui.notify("NER analysis complete!", type="positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"NER error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/ner")
        config.save()

    ui.button("Run NER", on_click=run_ner, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route in app.py, commit**

```bash
git add pages/ner.py app.py
git commit -m "feat: add NER page with NiceGUI"
```

---

### Task 14: Relationship Extraction page

**Files:**
- Create: `pages/relationships.py`
- Modify: `app.py`

- [ ] **Step 1: Implement Relationships page**

Create `pages/relationships.py`:

```python
"""Relationship extraction page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig
from NLP.relationship_extraction import process_files_for_relationships

ENTITY_TYPES = ["PERSON", "ORGANIZATION", "GPE", "LOCATION", "FACILITY", "DATE", "TIME", "MONEY", "PERCENT"]


def relationships_page():
    config = AppConfig()

    ui.label("Relationship Extraction").classes("text-h4")
    ui.label("Discover connections between entities in your documents").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    # Entity type selection
    ui.label("Entity Types").classes("text-subtitle2 q-mt-md")
    entity_select = ui.select(
        ENTITY_TYPES,
        multiple=True,
        label="Select entity types",
        value=["PERSON", "ORGANIZATION", "GPE"],
    ).classes("w-full")

    # Options
    with ui.row():
        extract_text = ui.checkbox("Extract text from PDFs", value=False)
        generate_graph = ui.checkbox("Generate network graph", value=True)

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_extraction():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return
        if not entity_select.value:
            ui.notify("Please select at least one entity type.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Extracting relationships...")

        def do_extract():
            return process_files_for_relationships(
                input_dir=in_dir,
                output_dir=in_dir,
                model_name="detailed",
                extract_text=1 if extract_text.value else 0,
                generate_graph=1 if generate_graph.value else 0,
                entity_types=entity_select.value,
            )

        try:
            results = await run.io_bound(do_extract)

            if results["status"] == "success":
                msg = f"Found {results['relationship_count']} relationships across {results['file_count']} files."
                status_label.set_text(msg)
                ui.notify(msg, type="positive")
            elif results["status"] == "warning":
                status_label.set_text(results["message"])
                ui.notify(results["message"], type="warning")
            else:
                status_label.set_text(results["message"])
                ui.notify(results["message"], type="negative")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Extraction error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/relationships")
        config.save()

    ui.button("Extract Relationships", on_click=run_extraction, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route, commit**

```bash
git add pages/relationships.py app.py
git commit -m "feat: add Relationship Extraction page with NiceGUI"
```

---

### Task 15: Co-Word Analysis page

**Files:**
- Create: `pages/cowords.py`
- Modify: `app.py`

- [ ] **Step 1: Implement Co-Words page**

Create `pages/cowords.py`:

```python
"""Co-word analysis page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig
from NLP.co_word_analysis import main as co_word_main


def cowords_page():
    config = AppConfig()

    ui.label("Co-Word Analysis").classes("text-h4")
    ui.label("Generate word co-occurrence networks to reveal conceptual relationships").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    ui.separator()

    progress = ui.linear_progress(value=0).classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_coword():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Running co-word analysis...")

        try:
            await run.io_bound(co_word_main, in_dir)
            status_label.set_text("Co-word analysis complete! Results saved in input directory.")
            ui.notify("Co-word analysis complete!", type="positive")

            # Check for summary file
            summary = os.path.join(in_dir, "Co_Word_Analysis_Summary.html")
            if os.path.exists(summary):
                ui.label("Summary report generated.").classes("text-positive")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Co-word analysis error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("last_page", "/cowords")
        config.save()

    ui.button("Run Analysis", on_click=run_coword, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route, commit**

```bash
git add pages/cowords.py app.py
git commit -m "feat: add Co-Word Analysis page with NiceGUI"
```

---

### Task 16: RAG Chat page

**Files:**
- Create: `pages/rag.py`
- Modify: `app.py`

- [ ] **Step 1: Implement RAG page**

Create `pages/rag.py`:

```python
"""RAG chatbot page."""
import os
from nicegui import ui, run
import webview
from config import AppConfig, get_models_dir


def rag_page():
    config = AppConfig()
    rag_state = {"system": None, "initialized": False}

    ui.label("RAG Chat").classes("text-h4")
    ui.label("Chat with your documents using Llama AI").classes("text-subtitle1")
    ui.separator()

    # Setup section
    with ui.card().classes("w-full") as setup_card:
        doc_dir = ui.input("Documents Directory").classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_dir(doc_dir), icon="folder_open").props("flat")

        model_path = ui.input(
            "Model File (.gguf)",
            value=config.get("defaults.rag_model_path", ""),
        ).classes("w-full")
        ui.button("Browse...", on_click=lambda: _browse_file(model_path), icon="folder_open").props("flat")

        init_status = ui.label("Not initialized")
        init_progress = ui.linear_progress(value=0).classes("w-full")
        init_progress.set_visibility(False)

    # Chat section (hidden until initialized)
    chat_container = ui.column().classes("w-full")
    chat_container.set_visibility(False)

    async def initialize_rag():
        if not doc_dir.value:
            ui.notify("Please select a documents directory.", type="warning")
            return
        if not model_path.value or not os.path.exists(model_path.value):
            ui.notify("Please select a valid model file.", type="warning")
            return

        init_progress.set_visibility(True)
        init_status.set_text("Loading model and indexing documents...")

        def do_init():
            from RAG.llama32_rag import Llama32RAGSystem
            return Llama32RAGSystem(
                documents_dir=doc_dir.value,
                llm_model_path=model_path.value,
                verbose=False,
            )

        try:
            rag_state["system"] = await run.io_bound(do_init)
            rag_state["initialized"] = True
            init_status.set_text("RAG system ready!")
            init_progress.set_visibility(False)
            setup_card.set_visibility(False)
            chat_container.set_visibility(True)

            # Build chat UI
            with chat_container:
                ui.chat_message(
                    "Hello! I've indexed your documents. Ask me anything about them.",
                    name="Assistant",
                    stamp="System",
                ).props("bg-color=blue-2")

                message_input = ui.input(placeholder="Type your question...").classes("w-full")
                send_btn = ui.button("Send", icon="send").props("color=primary")

                async def send_message():
                    question = message_input.value
                    if not question:
                        return

                    message_input.set_value("")
                    ui.chat_message(question, name="You", sent=True)

                    send_btn.disable()
                    thinking = ui.chat_message("Thinking...", name="Assistant").props("bg-color=blue-2")

                    def do_query():
                        return rag_state["system"].query(question)

                    try:
                        result = await run.io_bound(do_query)
                        chat_container.remove(thinking)

                        answer = result["answer"]
                        sources_text = ""
                        if result.get("sources"):
                            unique = {}
                            for s in result["sources"]:
                                key = os.path.basename(s["source"])
                                if s.get("page") is not None:
                                    key += f" (p.{s['page']})"
                                unique[key] = True
                            sources_text = "\n\nSources: " + ", ".join(unique.keys())

                        ui.chat_message(
                            answer + sources_text,
                            name="Assistant",
                            stamp=f"{result.get('processing_time', 0):.1f}s",
                        ).props("bg-color=blue-2")
                    except Exception as e:
                        chat_container.remove(thinking)
                        ui.chat_message(f"Error: {e}", name="Assistant").props("bg-color=red-2")
                    finally:
                        send_btn.enable()

                send_btn.on_click(send_message)
                message_input.on("keydown.enter", send_message)

            config.set("defaults.rag_model_path", model_path.value)
            config.set("last_page", "/rag")
            config.save()

        except Exception as e:
            init_status.set_text(f"Error: {e}")
            init_progress.set_visibility(False)
            ui.notify(f"Failed to initialize RAG: {e}", type="negative")

    ui.button("Initialize RAG", on_click=initialize_rag, icon="play_arrow").props("color=primary")


def _browse_dir(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        target_input.set_value(result[0])


def _browse_file(target_input: ui.input):
    result = webview.windows[0].create_file_dialog(
        webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=("GGUF Models (*.gguf)",),
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
```

- [ ] **Step 2: Wire route, commit**

```bash
git add pages/rag.py app.py
git commit -m "feat: add RAG Chat page with NiceGUI"
```

---

## Chunk 6: Cleanup & PyInstaller

### Task 17: Remove old Tkinter files

**Files:**
- Delete: all `*Window.py`, all `*.ui` files

- [ ] **Step 1: Delete old window and UI files**

```bash
git rm defaultWindow.py aksWindow.py ocrWindow.py audioTranscriptionWindow.py \
      translationWindow.py nerWindow.py coWordAnalysisWindow.py \
      relationshipExtractionWindow.py ragWindow.py
git rm defaultWindow.ui aksWindow.ui ocrWindow.ui audioTranscriptionWindow.ui \
      translationWindow.ui nerWindow.ui coWordAnalysisWindow.ui \
      relationshipExtractionWindow.ui ragWindow.ui
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove old Pygubu/Tkinter window and UI files"
```

---

### Task 18: PyInstaller packaging

**Files:**
- Create: `mdmt.spec`

- [ ] **Step 1: Create PyInstaller spec file**

Create `mdmt.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect data files for frameworks that bundle static assets
nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Assets', 'Assets'),
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# Hidden imports — PyInstaller can't discover these via static analysis
hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
    # ML/NLP deps that use dynamic imports
    'ocrmypdf',
    'googletrans',
    'langchain',
    'langchain_community',
    'sentence_transformers',
    'transformers',
    'nltk',
    'networkx',
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# Use --onedir mode (COLLECT) for large ML apps — avoids multi-GB extraction on each launch.
# Switch to single-file EXE if the dependency footprint is reduced later.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mdmt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='Assets/starNymph.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='mdmt',
)
```

Note: This uses `--onedir` mode (COLLECT) rather than single-file because the heavy ML dependencies (torch, transformers, langchain) would make a single-file executable extremely large and slow to start. The output in `dist/mdmt/` is a directory containing `mdmt` (the executable) plus all dependencies. This can be distributed as a zip or installer. If you want to explore single-file mode later, remove the `exclude_binaries=True` and `COLLECT` block and add binaries/datas back to `EXE`.

**Important:** The PyInstaller spec will likely need iterative refinement. Run the build, test the output, and add missing hidden imports or data files as discovered. This is normal for large Python apps with ML dependencies.

- [ ] **Step 2: Install PyInstaller**

Run: `source .venv/bin/activate && pip install pyinstaller`

- [ ] **Step 3: Build the executable**

Run: `source .venv/bin/activate && pyinstaller mdmt.spec`
Expected: Build completes and produces `dist/mdmt` executable.

- [ ] **Step 4: Test the executable**

Run: `./dist/mdmt`
Verify: App launches with native window, sidebar navigation works, pages load correctly.

- [ ] **Step 5: Commit**

```bash
git add mdmt.spec
git commit -m "feat: add PyInstaller spec for single-file executable build"
```

---

### Task 19: Final integration test

- [ ] **Step 1: Run all tests**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run the app from source**

Run: `source .venv/bin/activate && python app.py`

Manual verification checklist:
- [ ] App opens in native window
- [ ] Sidebar navigation works for all pages
- [ ] OCR page: browse dialogs work, language list populates
- [ ] Audio page: model selection works
- [ ] Translation page: language dropdown populates
- [ ] Keywords page: input fields and options work
- [ ] NER page: directory selection works
- [ ] Relationships page: entity type multi-select works
- [ ] Co-Words page: directory selection works
- [ ] RAG page: model file browser filters .gguf files
- [ ] Downloads page: shows installed/not-installed status
- [ ] About page: renders help and about info

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete MDMT web UI conversion from Pygubu to NiceGUI"
```
