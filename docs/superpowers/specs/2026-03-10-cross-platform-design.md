# Cross-Platform Compatibility Design

**Date:** 2026-03-10
**Goal:** Ensure MDMT runs on macOS, Windows, and Linux with PyInstaller-based distribution and GitHub Actions CI.
**Approach:** Minimal fixes + per-platform PyInstaller specs (Approach 1 — surgical changes to an already well-structured codebase).

## Current State

The codebase is already ~90% cross-platform:
- `platformdirs` for app data directories
- `os.path.join()` for all path construction
- Platform-aware GPU detection with fallbacks
- Native file dialogs via pywebview
- Platform-conditional dependencies in requirements.txt

## Runtime Fixes

### 1. Multiprocessing Start Method (app.py)
Replace hardcoded `'fork'` with platform-aware logic. Use `'spawn'` on Windows (the only supported method), `'fork'` on Linux/macOS.

### 2. UTF-8 Encoding on open() Calls
Add `encoding='utf-8'` to all `open()` calls missing it. Windows defaults to `cp1252`, which breaks on UTF-8 content.

Files affected:
- `config.py` — config read (line 52) and write (line 82)
- `Advanced_Keyword_Search/advancedKeywordSearchLogic.py` — keyword file read (line 48) and filter file read (line 143)

### 3. Hardcoded Developer Paths (NLP modules)
Replace hardcoded `/home/james/...` paths in `__main__` blocks with relative paths:
- `NLP/co_word_analysis.py:198`
- `NLP/named_entity_recognition.py:224`

### 4. Bundled Tesseract PATH Setup (app.py)
When running as a frozen PyInstaller bundle (`getattr(sys, 'frozen', False)`), prepend the bundled Tesseract directory to `PATH` and set `TESSDATA_PREFIX` so `ocrmypdf` can discover it.

### 5. Tesseract Path Helper (config.py)
Add `get_tesseract_path()` that checks for a bundled Tesseract first (relative to the frozen executable), then falls back to system PATH.

## PyInstaller Platform Specs

Rename `mdmt.spec` to `mdmt-linux.spec` and create two new spec files.

### Common Structure
All three specs share:
- `app.py` entry point
- NiceGUI data files collection
- Hidden imports for ML/NLP dynamic imports
- `--onedir` mode (avoids multi-GB extraction on launch)

### Per-Platform Differences

| | Linux | macOS | Windows |
|---|---|---|---|
| **Tesseract source** | `/usr/bin/tesseract` + shared libs | Homebrew install | `C:\Program Files\Tesseract-OCR` |
| **Icon** | `MDMT_logo.png` | `MDMT_logo.png` | `MDMT_logo.ico` |
| **GUI backend** | PyQt6 (bundled via requirements) | Cocoa (pywebview default) | EdgeChromium (pywebview default) |

Each spec bundles:
- Tesseract binary
- Required shared libraries for Tesseract
- Baseline `eng.traineddata` (additional languages via Downloads page at runtime)

### Icon
- Source: `MDMT_logo.png` (project root)
- Windows requires `.ico` format: generate `MDMT_logo.ico`

## GitHub Actions CI Pipeline

### Workflow: `.github/workflows/build.yml`

**Triggers:**
- Tag push matching `v*` (releases)
- Manual `workflow_dispatch` (testing)

**Jobs (parallel):**

#### build-linux (ubuntu-latest)
1. Checkout + Python 3.12
2. `apt-get install tesseract-ocr`
3. `pip install -r requirements.txt`
4. `pytest`
5. `pyinstaller mdmt-linux.spec`
6. Upload artifact

#### build-macos (macos-latest)
1. Checkout + Python 3.12
2. `brew install tesseract`
3. `pip install -r requirements.txt`
4. `pytest`
5. `pyinstaller mdmt-macos.spec`
6. Upload artifact

#### build-windows (windows-latest)
1. Checkout + Python 3.12
2. `choco install tesseract`
3. `pip install -r requirements.txt` (llama-cpp-python built with MSVC)
4. `pytest`
5. `pyinstaller mdmt-windows.spec`
6. Upload artifact

#### release (after all builds pass, on tag push only)
1. Download all three artifacts
2. Create GitHub Release
3. Attach: `mdmt-linux-x86_64.zip`, `mdmt-macos-arm64.zip`, `mdmt-windows-x64.zip`

### llama-cpp-python Build
- Linux/macOS: standard C++ toolchain on CI runners
- Windows: MSVC build tools + CMake (pre-installed on windows-latest)
- All platforms build from the git fork

## Files Changed

| File | Change Type |
|---|---|
| `app.py` | Edit — multiprocessing fix + frozen Tesseract PATH setup |
| `config.py` | Edit — UTF-8 encoding + `get_tesseract_path()` |
| `Advanced_Keyword_Search/advancedKeywordSearchLogic.py` | Edit — UTF-8 encoding |
| `NLP/co_word_analysis.py` | Edit — relative path in `__main__` |
| `NLP/named_entity_recognition.py` | Edit — relative path in `__main__` |
| `mdmt.spec` → `mdmt-linux.spec` | Rename + edit — Tesseract bundling |
| `mdmt-macos.spec` | New — macOS PyInstaller spec |
| `mdmt-windows.spec` | New — Windows PyInstaller spec |
| `MDMT_logo.ico` | New — Windows icon |
| `.github/workflows/build.yml` | New — CI pipeline |
