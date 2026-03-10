# MDMT Web UI Conversion Design

**Date:** 2026-03-09
**Status:** Approved

## Overview

Convert MDMT from a Pygubu/Tkinter desktop GUI to a NiceGUI-based web UI, distributed as a single PyInstaller executable with a native window (pywebview).

## Goals & Constraints

- **Primary goal:** Easier deployment — single executable binary via PyInstaller
- **Usage model:** Single user, local (localhost)
- **UX direction:** Modernize the interface (sidebar navigation, drag-and-drop, inline results)
- **Tech constraint:** Python-only — no JavaScript/TypeScript to maintain
- **Large assets:** Downloaded on demand from upstream sources, not bundled

## Framework Choice: NiceGUI

**Why NiceGUI:**
- Pure Python — no HTML/JS/CSS to write or maintain
- Built-in modern UI components (tabs, sidebar, cards, progress bars, file upload, chat)
- Native window mode via `ui.run(native=True)` + pywebview
- Documented PyInstaller support
- `run.cpu_bound()` / `run.io_bound()` utilities replace manual threading
- Active development, growing community

**Alternatives considered:**
- **Streamlit:** Page re-runs on every interaction; poor fit for stateful RAG chat; difficult PyInstaller bundling
- **Flask + HTMX:** Maximum flexibility but requires HTML/Jinja2 templates + CSS; doesn't match Python-only preference

## Application Structure

### Navigation

Persistent sidebar replacing the current hub-of-buttons launcher:

```
Sidebar                  Content Area
─────────────           ─────────────────────
Document Processing     Active module's UI
  OCR
  Audio Transcription
  Translation

Analysis
  Advanced Keywords
  NER
  Relationships
  Co-Words

AI
  RAG Chat

Settings
  Downloads
  Help
  About / License
```

### File Mapping

```
CURRENT (replaced)                    NEW
──────────────────────               ──────────────────────
defaultWindow.py + .ui        →     app.py (entry point + sidebar)
aksWindow.py + .ui            →     pages/keywords.py
ocrWindow.py + .ui            →     pages/ocr.py
audioTranscriptionWindow.py   →     pages/audio.py
translationWindow.py + .ui    →     pages/translation.py
nerWindow.py + .ui            →     pages/ner.py
relationshipExtractionWindow  →     pages/relationships.py
coWordAnalysisWindow.py + .ui →     pages/cowords.py
ragWindow.py + .ui            →     pages/rag.py
(new)                         →     pages/downloads.py
```

All `.ui` XML files are deleted (no longer needed).

### Backend Logic

**Already separated (unchanged):**
- `Advanced_Keyword_Search/advancedKeywordSearchLogic.py`
- `NLP/named_entity_recognition.py`
- `NLP/relationship_extraction.py`
- `NLP/co_word_analysis.py`
- `RAG/llama32_rag.py`
- `Translation/googletranslateWrapper.py`

**Requires extraction (business logic currently embedded in window files):**
- `ocrWindow.py` → extract `ocrmypdf` calls, language dictionary, file walking, and directory duplication logic into new `OCR/ocr_logic.py`
- `audioTranscriptionWindow.py` → extract Whisper model loading and transcription calls into new `Audio_Transcription/transcription_logic.py`
- `translationWindow.py` → extract `LANGUAGE_CODES` dictionary and file-handling orchestration into `Translation/googletranslateWrapper.py` (extend existing module)

## File & Directory Selection

Since this is a local app running via pywebview, file/directory selection uses **pywebview's native file dialog API** rather than NiceGUI's web-oriented upload component:

```python
import webview

# File selection (returns list of file paths)
result = webview.windows[0].create_file_dialog(
    webview.OPEN_DIALOG,
    allow_multiple=True,
    file_types=('PDF Files (*.pdf)',)
)

# Directory selection
result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
```

This gives users native OS file picker dialogs — familiar and direct access to local paths without copying files through an upload pipeline. Each module page wraps these in helper functions triggered by "Browse" buttons.

For drag-and-drop convenience on input files, NiceGUI's `ui.upload()` can be used as an alternative input method alongside the native file picker. Uploaded files are written to a temp directory and the path is passed to the backend logic.

## Error Handling

Replace `tkinter.messagebox` with a consistent NiceGUI pattern:

- **Transient errors** (invalid input, missing files): `ui.notify('message', type='warning')` — toast notification
- **Processing errors** (OCR failure, model error): `ui.notify('message', type='negative')` — red toast, plus inline error state on the results area
- **Fatal errors** (missing dependencies, corrupt config): `ui.dialog()` — modal dialog requiring acknowledgment

All error messages follow the same format: what went wrong + what to do about it.

## First-Run Experience

On first launch (no `config.json` exists):

1. App opens to a **Welcome page** that briefly explains MDMT
2. Welcome page shows which optional assets are available and their status
3. User can download assets now or skip — modules will show inline warnings when required assets are missing (e.g., "Tesseract English language data required — [Download now]")
4. After dismissing welcome, the sidebar is fully navigable; no modules are blocked, just degraded with clear messaging

On subsequent launches, the app opens to the last-visited page (stored in `config.json`).

## Module Designs

### OCR Module (`pages/ocr.py`)
- Drag-and-drop file upload (multi-file)
- Output directory selector
- Language dropdown (populated from available tessdata)
- Option checkboxes: deskew, rotate, force OCR, PDF/A output, extract text
- Run button with per-file progress tracking
- Results table showing status of each processed file

### RAG Chat Module (`pages/rag.py`)
- Model selector dropdown
- Document management (add files, rebuild index) integrated into page
- NiceGUI `ui.chat_message()` component for conversation display
- Source citations shown inline with messages
- Text input + send button

### Advanced Keyword Search (`pages/keywords.py`)
- Input/output directory selectors
- Editable keyword and filter lists (text areas, one per line)
- Context word count selector
- Inline results table with keyword counts and KWIC links
- In-app chart viewing (matplotlib/plotly integration)
- CSV download button

### NER, Relationship Extraction, Co-Word Analysis
Common pattern: file upload → configure options → run → inline results display.

- Network graphs and visualizations rendered inline (NiceGUI plotly/matplotlib)
- Results tables shown directly in the page
- Export buttons (CSV, JSON, HTML) trigger browser downloads

### Audio Transcription (`pages/audio.py`)
- Drag-and-drop audio file upload
- Model size selector (tiny, base, small, medium)
- Progress bar during transcription
- Inline transcript display with copy/download buttons

### Translation (`pages/translation.py`)
- File upload for source documents
- Source/target language selectors
- Output configuration
- Inline translation preview
- Download translated file

### Downloads / Asset Manager (`pages/downloads.py`)
Downloads from official upstream sources — no self-hosting:

- **LLM Models:** HuggingFace Hub via `huggingface_hub` library
- **Tesseract languages:** GitHub tessdata releases
- **Whisper models:** Whisper's built-in download mechanism, with `download_root` pointed to `<app_data>/whisper_models/` instead of the default `~/.cache/whisper/` to keep all assets in one managed location
- **NLTK data:** `nltk.download()` with `download_dir` pointed to `<app_data>/nltk_data/`

UI shows:
- Available models/languages with sizes
- Download status (not downloaded / downloading / installed)
- Checkboxes for batch selection
- Download progress bars

## PyInstaller Packaging & File Storage

### App Data Directory

Using `platformdirs` for cross-platform paths:

```
Linux:    ~/.local/share/mdmt/
macOS:    ~/Library/Application Support/mdmt/
Windows:  C:\Users\<user>\AppData\Local\mdmt\
```

Directory structure:

```
<app_data>/
├── models/            Llama models (downloaded from HuggingFace)
├── tessdata/          Tesseract language files (downloaded from GitHub)
├── whisper_models/    Whisper models (redirected from ~/.cache/whisper/)
├── nltk_data/         NLTK data (downloaded via nltk)
├── index/             RAG FAISS vector indices
└── config.json        User preferences
```

### `config.json` Schema

```json
{
  "last_page": "/ocr",
  "defaults": {
    "ocr_language": "eng",
    "ocr_output_dir": "/home/user/ocr_output",
    "aks_input_dir": null,
    "aks_output_dir": null,
    "whisper_model": "tiny",
    "translation_target_lang": "en",
    "rag_model_path": null
  },
  "window": {
    "width": 1200,
    "height": 800
  }
}
```

Defaults are `null` until the user sets them. Each module reads its relevant defaults on page load and writes them back on successful run.

### PyInstaller Bundle Contents

**Included:**
- All Python code and dependencies
- NiceGUI + pywebview runtime
- Static assets (icons, images)

**Not included (downloaded on demand):**
- Llama model (~2.3 GB)
- Tesseract language files (~12-15 MB each)
- Whisper models (75 MB - 1.5 GB)
- NLTK data

## Dependency Changes

**Added:**
- `nicegui` — web UI framework
- `pywebview` — native window embedding
- `platformdirs` — cross-platform app data paths
- `huggingface_hub` — model downloads

**Removed:**
- `pygubu` — no longer needed

## Threading Model Change

- **Current:** Manual `threading.Thread` + `self.mainwindow.after()` for UI updates
- **New:** NiceGUI's async utilities handle background work and UI updates automatically

**Per-module strategy:**
- `run.io_bound()` (thread pool) — for most modules: OCR, Audio Transcription, Translation, AKS, NER, Relationship Extraction, Co-Word Analysis. Also for RAG queries, since the RAG system holds large in-memory state (FAISS index, loaded LLM) that is not picklable.
- `run.cpu_bound()` (process pool) — reserved for pure computation tasks where the callable and arguments are fully picklable. Not suitable for the RAG module's stateful `Llama32RAGSystem` class.

The RAG system's lifecycle (load model once, query many times) is managed by holding the `Llama32RAGSystem` instance in the page's state and running queries via `run.io_bound()`.

## Implementation Milestones

**Milestone 0 — Proof of Concept (do first):**
Build a minimal NiceGUI app with `native=True` + PyInstaller bundling to validate the stack before committing to the full conversion. The PoC should demonstrate:
- Native window opens with a NiceGUI page
- A pywebview file dialog works from a NiceGUI button
- `run.io_bound()` runs a background task with progress feedback
- PyInstaller produces a working single-file executable

This de-risks the core technical assumptions before investing in the full migration.

**Milestone 1 — Backend extraction:** Extract embedded logic from OCR, Audio, and Translation window files into standalone backend modules.

**Milestone 2 — App shell:** `app.py` with sidebar navigation, page routing, app data directory setup, config loading, and the Downloads page.

**Milestone 3 — Module migration:** Port each module one at a time, starting with the simplest (Audio Transcription) and ending with the most complex (RAG Chat).

**Milestone 4 — PyInstaller packaging:** Build the single executable with all dependencies bundled.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  PyInstaller Binary                      │
│                                                          │
│  app.py (entry point)                                    │
│  ├── NiceGUI native=True (pywebview window)              │
│  ├── Sidebar layout + page routing                       │
│  └── App data init via platformdirs                      │
│                                                          │
│  pages/  (NEW)              Backend Logic (UNCHANGED)    │
│  ├── ocr.py            ──→  OCR / ocrmypdf               │
│  ├── audio.py          ──→  Whisper                      │
│  ├── translation.py    ──→  Translation/                 │
│  ├── keywords.py       ──→  Advanced_Keyword_Search/     │
│  ├── ner.py            ──→  NLP/named_entity_recognition │
│  ├── relationships.py  ──→  NLP/relationship_extraction  │
│  ├── cowords.py        ──→  NLP/co_word_analysis         │
│  ├── rag.py            ──→  RAG/llama32_rag              │
│  └── downloads.py      ──→  huggingface_hub / urllib     │
│                                                          │
└──────────────────────────┬──────────────────────────────┘
                           │ reads/writes
            ┌──────────────▼──────────────────┐
            │  ~/.local/share/mdmt/            │
            │  ├── models/    (from HF)        │
            │  ├── tessdata/  (from GitHub)    │
            │  ├── nltk_data/ (from nltk)      │
            │  ├── index/     (FAISS indices)  │
            │  └── config.json                 │
            └─────────────────────────────────┘
```
