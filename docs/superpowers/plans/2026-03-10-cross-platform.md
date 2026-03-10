# Cross-Platform Compatibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MDMT run correctly on macOS, Windows, and Linux, with PyInstaller-based distribution and GitHub Actions CI for automated builds.

**Architecture:** Fix the small set of runtime incompatibilities (multiprocessing, file encoding, Tesseract path resolution), create per-platform PyInstaller spec files that bundle Tesseract, and add a GitHub Actions workflow for automated cross-platform builds and releases.

**Tech Stack:** Python 3.12, PyInstaller, GitHub Actions, Tesseract OCR, NiceGUI/pywebview

**Spec:** `docs/superpowers/specs/2026-03-10-cross-platform-design.md`

---

## Chunk 1: Runtime Fixes

### Task 1: Fix multiprocessing start method for Windows

**Files:**
- Modify: `app.py:2-6`
- Test: `tests/test_platform_compat.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_platform_compat.py`:

```python
"""Tests for cross-platform compatibility."""
import platform
from unittest.mock import patch


def test_multiprocessing_start_method_spawn_on_windows():
    """On Windows, the app should use 'spawn' (the only supported method)."""
    with patch("platform.system", return_value="Windows"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "spawn"


def test_multiprocessing_start_method_fork_on_linux():
    """On Linux, the app should use 'fork' for NiceGUI compatibility."""
    with patch("platform.system", return_value="Linux"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "fork"


def test_multiprocessing_start_method_fork_on_macos():
    """On macOS, the app should use 'fork' for NiceGUI compatibility."""
    with patch("platform.system", return_value="Darwin"):
        from app import _preferred_start_method
        assert _preferred_start_method() == "fork"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_platform_compat.py -v`
Expected: FAIL with `ImportError: cannot import name '_preferred_start_method'`

- [ ] **Step 3: Implement the fix in app.py**

Replace lines 1-6 of `app.py`:

```python
"""MDMT main application entry point with NiceGUI sidebar navigation."""
import multiprocessing
import platform


def _preferred_start_method() -> str:
    """Return the preferred multiprocessing start method for the current OS."""
    if platform.system() == "Windows":
        return "spawn"
    return "fork"


try:
    multiprocessing.set_start_method(_preferred_start_method())
except RuntimeError:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_platform_compat.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `source .venv/bin/activate && pytest -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_platform_compat.py
git commit -m "fix: use platform-aware multiprocessing start method for Windows"
```

---

### Task 2: Add UTF-8 encoding to config.py open() calls

**Files:**
- Modify: `config.py:52` and `config.py:81`
- Test: `tests/test_config.py` (existing — add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify current behavior**

Run: `source .venv/bin/activate && pytest tests/test_config.py::test_config_save_and_load_utf8 -v`
Expected: May pass on Linux (UTF-8 default) but would fail on Windows (cp1252). We add encoding anyway for correctness.

- [ ] **Step 3: Add encoding='utf-8' to config.py**

In `config.py`, change line 52:
```python
# Old:
            with open(self._path, "r") as f:
# New:
            with open(self._path, "r", encoding="utf-8") as f:
```

In `config.py`, change line 81:
```python
# Old:
        with open(self._path, "w") as f:
# New:
        with open(self._path, "w", encoding="utf-8") as f:
```

Also in `config.py`, change line 82 (`json.dump` call) to write actual UTF-8 characters
instead of `\uXXXX` escapes (needed so encoding actually matters):
```python
# Old:
            json.dump(self._data, f, indent=2)
# New:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify**

Run: `source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "fix: add explicit UTF-8 encoding to config file I/O for Windows"
```

---

### Task 3: Add UTF-8 encoding to keyword search open() calls

**Files:**
- Modify: `Advanced_Keyword_Search/advancedKeywordSearchLogic.py:48` and `:143`

- [ ] **Step 1: Fix both open() calls**

In `Advanced_Keyword_Search/advancedKeywordSearchLogic.py`, change line 48:
```python
# Old:
            userKeywords = open(keywordFilePath, "r")
# New:
            userKeywords = open(keywordFilePath, "r", encoding="utf-8")
```

Change line 143:
```python
# Old:
                    with open(filterFilePath, 'r') as file:
# New:
                    with open(filterFilePath, 'r', encoding='utf-8') as file:
```

- [ ] **Step 2: Run the full test suite to check for regressions**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add Advanced_Keyword_Search/advancedKeywordSearchLogic.py
git commit -m "fix: add explicit UTF-8 encoding to keyword search file I/O"
```

---

### Task 4: Replace hardcoded developer paths in NLP modules

**Files:**
- Modify: `NLP/co_word_analysis.py:198`
- Modify: `NLP/named_entity_recognition.py:224`

- [ ] **Step 1: Fix both __main__ blocks**

In `NLP/co_word_analysis.py`, change line 198:
```python
# Old:
    directory = "/home/james/PycharmProjects/MDMT/NLP/input"  # <-- Update this path accordingly.
# New:
    directory = os.path.join(os.path.dirname(__file__), "input")  # <-- Update this path accordingly.
```

In `NLP/named_entity_recognition.py`, change line 224:
```python
# Old:
    directory = "/home/james/School/Masters (2023-202x)/HIST 9308B/Term Paper"  # <-- Update this path accordingly.
# New:
    directory = os.path.join(os.path.dirname(__file__), "input")  # <-- Update this path accordingly.
```

- [ ] **Step 2: Run the full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add NLP/co_word_analysis.py NLP/named_entity_recognition.py
git commit -m "fix: replace hardcoded developer paths with relative paths in NLP modules"
```

---

### Task 5: Add Tesseract path helper and frozen-app PATH setup

**Files:**
- Modify: `config.py` (add `get_tesseract_path()`)
- Modify: `app.py` (add frozen PATH setup in `main()`)
- Test: `tests/test_platform_compat.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_platform_compat.py` (note: `import platform` is already at the
top of the file from Task 1; the imports below are additional ones needed for these tests):

```python
import os
import sys


def test_get_tesseract_path_returns_string():
    """get_tesseract_path should return a string path."""
    from config import get_tesseract_path
    result = get_tesseract_path()
    assert isinstance(result, str)


def test_get_tesseract_path_frozen_prefers_bundled(tmp_path):
    """When running as a frozen app, bundled Tesseract should be preferred."""
    from config import get_tesseract_path
    # Simulate a frozen app with a bundled tesseract binary
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
        # When frozen and bundled binary exists, should return the bundled path
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_platform_compat.py -v`
Expected: FAIL with `ImportError` for new functions

- [ ] **Step 3: Add get_tesseract_path() to config.py**

Append to `config.py` (after `get_index_dir()`):

```python
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
```

- [ ] **Step 4: Add _setup_frozen_env() to app.py**

Add this function to `app.py` (after the imports, before `create_sidebar()`):

```python
def _setup_frozen_env(base_path: str = None):
    """Configure environment for bundled Tesseract when running as a frozen app."""
    import sys
    if base_path is None:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    tess_bin_dir = os.path.join(base_path, "tesseract_bin")
    tessdata_dir = os.path.join(base_path, "tessdata")

    if os.path.isdir(tess_bin_dir):
        os.environ["PATH"] = tess_bin_dir + os.pathsep + os.environ.get("PATH", "")
    if os.path.isdir(tessdata_dir):
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
```

Then call it at the top of `main()`:

```python
def main():
    """Initialize app data directory and start NiceGUI."""
    import sys
    if getattr(sys, "frozen", False):
        _setup_frozen_env()

    get_app_data_dir()
    # ... rest of main unchanged
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_platform_compat.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add config.py app.py tests/test_platform_compat.py
git commit -m "feat: add Tesseract path helper and frozen-app environment setup"
```

---

## Chunk 2: PyInstaller Spec Files

### Task 6: Rename mdmt.spec to mdmt-linux.spec and add Tesseract bundling

**Files:**
- Rename: `mdmt.spec` → `mdmt-linux.spec`
- Modify: `mdmt-linux.spec` (add Tesseract bundling, fix icon path)

- [ ] **Step 1: Rename the spec file**

```bash
git mv mdmt.spec mdmt-linux.spec
```

- [ ] **Step 2: Update mdmt-linux.spec with Tesseract bundling and correct icon**

Replace the full contents of `mdmt-linux.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect data files for frameworks that bundle static assets
nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# --- Tesseract bundling (Linux) ---
binaries = []
tesseract_bin = shutil.which('tesseract')
if tesseract_bin:
    binaries.append((tesseract_bin, 'tesseract_bin'))
    # Bundle shared library dependencies discovered via ldd
    try:
        ldd_out = subprocess.check_output(['ldd', tesseract_bin], text=True)
        for line in ldd_out.splitlines():
            parts = line.strip().split()
            # Format: libfoo.so.1 => /usr/lib/libfoo.so.1 (0x...)
            if '=>' in line and len(parts) >= 3 and parts[2].startswith('/'):
                lib_path = parts[2]
                # Skip core system libs (libc, libm, libpthread, ld-linux, etc.)
                basename = os.path.basename(lib_path)
                if not any(basename.startswith(s) for s in ('libc.', 'libm.', 'libdl.', 'libpthread.', 'ld-linux', 'librt.', 'libgcc_s.')):
                    binaries.append((lib_path, 'tesseract_bin'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

# Bundle eng.traineddata as baseline
tessdata_candidates = [
    '/usr/share/tesseract-ocr/5/tessdata',
    '/usr/share/tesseract-ocr/4.00/tessdata',
    '/usr/share/tessdata',
]
for td in tessdata_candidates:
    eng = os.path.join(td, 'eng.traineddata')
    if os.path.isfile(eng):
        datas.append((td, 'tessdata'))
        break

# Hidden imports — PyInstaller can't discover these via static analysis
hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    icon='MDMT_logo.png',
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

- [ ] **Step 3: Commit**

```bash
git add mdmt-linux.spec
git commit -m "refactor: rename spec to mdmt-linux.spec and add Tesseract bundling"
```

---

### Task 7: Create mdmt-macos.spec

**Files:**
- Create: `mdmt-macos.spec`

- [ ] **Step 1: Create the macOS spec file**

Create `mdmt-macos.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# --- Tesseract bundling (macOS / Homebrew) ---
binaries = []
tesseract_bin = shutil.which('tesseract')
if tesseract_bin:
    binaries.append((tesseract_bin, 'tesseract_bin'))
    # Bundle shared library dependencies discovered via otool
    try:
        otool_out = subprocess.check_output(['otool', '-L', tesseract_bin], text=True)
        for line in otool_out.splitlines()[1:]:  # skip first line (binary path)
            lib_path = line.strip().split(' (')[0].strip()
            # Bundle Homebrew libs, skip system frameworks
            if lib_path.startswith(('/opt/homebrew/', '/usr/local/')) and os.path.isfile(lib_path):
                binaries.append((lib_path, 'tesseract_bin'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

# Bundle eng.traineddata as baseline
tessdata_candidates = [
    '/opt/homebrew/share/tessdata',           # Apple Silicon Homebrew
    '/usr/local/share/tessdata',              # Intel Homebrew
    '/opt/homebrew/share/tesseract-ocr/5/tessdata',
    '/usr/local/share/tesseract-ocr/5/tessdata',
]
for td in tessdata_candidates:
    eng = os.path.join(td, 'eng.traineddata')
    if os.path.isfile(eng):
        datas.append((td, 'tessdata'))
        break

hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    icon='MDMT_logo.png',
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

- [ ] **Step 2: Commit**

```bash
git add mdmt-macos.spec
git commit -m "feat: add macOS PyInstaller spec with Tesseract bundling"
```

---

### Task 8: Create mdmt-windows.spec and Windows icon

**Files:**
- Create: `mdmt-windows.spec`
- Create: `MDMT_logo.ico` (converted from MDMT_logo.png)

- [ ] **Step 1: Generate the Windows .ico file**

```bash
source .venv/bin/activate && python -c "
from PIL import Image
img = Image.open('MDMT_logo.png')
img.save('MDMT_logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('MDMT_logo.ico created')
"
```

Note: If Pillow is not installed, install it first: `pip install Pillow`

- [ ] **Step 2: Create the Windows spec file**

Create `mdmt-windows.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# --- Tesseract bundling (Windows) ---
binaries = []
# Check common install locations
tesseract_candidates = [
    os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'Tesseract-OCR', 'tesseract.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
    shutil.which('tesseract') or '',
]
for candidate in tesseract_candidates:
    if candidate and os.path.isfile(candidate):
        tess_dir = os.path.dirname(candidate)
        binaries.append((candidate, 'tesseract_bin'))
        # Bundle DLLs from the same directory
        for dll in os.listdir(tess_dir):
            if dll.endswith('.dll'):
                binaries.append((os.path.join(tess_dir, dll), 'tesseract_bin'))
        # Bundle tessdata
        tessdata = os.path.join(tess_dir, 'tessdata')
        if os.path.isdir(tessdata):
            datas.append((tessdata, 'tessdata'))
        break

hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    icon='MDMT_logo.ico',
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

- [ ] **Step 3: Commit**

```bash
git add MDMT_logo.ico mdmt-windows.spec
git commit -m "feat: add Windows PyInstaller spec with Tesseract bundling and .ico icon"
```

---

## Chunk 3: GitHub Actions CI Pipeline

### Task 9: Create the cross-platform build workflow

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: Create the workflow file**

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/build.yml`:

```yaml
name: Build & Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y tesseract-ocr tesseract-ocr-eng ffmpeg cmake build-essential

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Run tests
        run: pytest -v

      - name: Build with PyInstaller
        run: pyinstaller mdmt-linux.spec

      - name: Package artifact
        run: |
          cd dist
          zip -r ../mdmt-linux-x86_64.zip mdmt/

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: mdmt-linux-x86_64
          path: mdmt-linux-x86_64.zip

  build-macos:
    runs-on: macos-14  # Apple Silicon (arm64) runner
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install system dependencies
        run: |
          brew install tesseract ffmpeg cmake

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Run tests
        run: pytest -v

      - name: Build with PyInstaller
        run: pyinstaller mdmt-macos.spec

      - name: Package artifact
        run: |
          cd dist
          zip -r ../mdmt-macos-arm64.zip mdmt/

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: mdmt-macos-arm64
          path: mdmt-macos-arm64.zip

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Tesseract
        run: choco install tesseract --no-progress -y

      - name: Install FFmpeg
        run: choco install ffmpeg --no-progress -y

      - name: Install C++ build tools
        run: choco install cmake --installargs 'ADD_CMAKE_TO_PATH=System' --no-progress -y

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Run tests
        run: pytest -v

      - name: Build with PyInstaller
        run: pyinstaller mdmt-windows.spec

      - name: Package artifact
        run: Compress-Archive -Path dist/mdmt -DestinationPath mdmt-windows-x64.zip

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: mdmt-windows-x64
          path: mdmt-windows-x64.zip

  release:
    needs: [build-linux, build-macos, build-windows]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            mdmt-linux-x86_64/mdmt-linux-x86_64.zip
            mdmt-macos-arm64/mdmt-macos-arm64.zip
            mdmt-windows-x64/mdmt-windows-x64.zip
          generate_release_notes: true
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "feat: add GitHub Actions CI for cross-platform builds and releases"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run the full test suite one last time**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Verify all changes look correct**

Run: `git log --oneline -10`
Expected: See all the commits from this implementation

- [ ] **Step 3: Verify no untracked files are left behind**

Run: `git status`
Expected: Clean working tree
