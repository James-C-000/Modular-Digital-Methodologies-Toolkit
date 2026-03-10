# Licenses Section Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add comprehensive third-party dependency attribution to the about module's license expansion.

**Architecture:** Single edit to `pages/about.py` — replace the one-line license section with a `ui.markdown()` block containing an alphabetical table of all 26 runtime dependencies with name, license type, and clickable project link.

**Tech Stack:** NiceGUI (`ui.markdown()` for rendering markdown tables)

**Spec:** `docs/specs/2026-03-10-licenses-section-design.md`

---

## Chunk 1: Implementation

### Task 1: Add the licenses table to the about page

**Files:**
- Modify: `pages/about.py:260-262`

- [ ] **Step 1: Edit the license expansion block**

Replace lines 260-262 of `pages/about.py`:

```python
    # License
    with ui.expansion("License", icon="gavel").classes("w-full mt-2"):
        ui.markdown("See project LICENSE file for full license terms.")
```

With:

```python
    # License
    with ui.expansion("License", icon="gavel").classes("w-full mt-2"):
        ui.markdown("See project LICENSE file for full license terms.")
        ui.markdown("""
| Library | License | Project |
|---|---|---|
| BeautifulSoup4 | MIT | [crummy.com](https://www.crummy.com/software/BeautifulSoup/) |
| docx2txt | MIT | [GitHub](https://github.com/ankushshah89/python-docx2txt) |
| FAISS | MIT AND BSD-3-Clause | [GitHub](https://github.com/facebookresearch/faiss) |
| future | MIT | [GitHub](https://github.com/PythonCharmers/python-future) |
| googletrans | MIT | [GitHub](https://github.com/ssut/py-googletrans) |
| Hugging Face Hub | Apache-2.0 | [GitHub](https://github.com/huggingface/huggingface_hub) |
| LangChain (core, community, huggingface, text-splitters) | MIT | [GitHub](https://github.com/langchain-ai/langchain) |
| llama-cpp-python | MIT | [GitHub](https://github.com/abetlen/llama-cpp-python) |
| Matplotlib | PSF-2.0 | [GitHub](https://github.com/matplotlib/matplotlib) |
| NetworkX | BSD-3-Clause | [GitHub](https://github.com/networkx/networkx) |
| NiceGUI | MIT | [GitHub](https://github.com/zauberzeug/nicegui) |
| NLTK | Apache-2.0 | [GitHub](https://github.com/nltk/nltk) |
| OCRmyPDF | MPL-2.0 | [GitHub](https://github.com/ocrmypdf/OCRmyPDF) |
| OpenAI Whisper | MIT | [GitHub](https://github.com/openai/whisper) |
| openpyxl | MIT | [openpyxl.readthedocs.io](https://openpyxl.readthedocs.io/) |
| pandas | BSD-3-Clause | [GitHub](https://github.com/pandas-dev/pandas) |
| platformdirs | MIT | [GitHub](https://github.com/tox-dev/platformdirs) |
| psutil | BSD-3-Clause | [GitHub](https://github.com/giampaolo/psutil) |
| pypdf | BSD-3-Clause | [GitHub](https://github.com/py-pdf/pypdf) |
| PyQt6 / PyQt6-WebEngine | GPL-3.0-only | [riverbankcomputing.com](https://riverbankcomputing.com/software/pyqt/) |
| pywebview | BSD-3-Clause | [GitHub](https://github.com/r0x0r/pywebview) |
| QtPy | MIT | [GitHub](https://github.com/spyder-ide/qtpy) |
| Requests | Apache-2.0 | [GitHub](https://github.com/psf/requests) |
| Sentence-Transformers | Apache-2.0 | [GitHub](https://github.com/UKPLab/sentence-transformers) |
| Tesseract OCR | Apache-2.0 | [GitHub](https://github.com/tesseract-ocr/tesseract) |
| Transformers (HuggingFace) | Apache-2.0 | [GitHub](https://github.com/huggingface/transformers) |
""")
```

- [ ] **Step 2: Verify the app loads without errors**

Run:
```bash
source .venv/bin/activate && timeout 10 python app.py || true
```

Expected: App starts without import errors or syntax errors. The timeout will kill it after 10 seconds — we just need to confirm it doesn't crash on startup.

- [ ] **Step 3: Visually verify the table renders**

Run the app (`python app.py`), navigate to the About page, expand the "License" section, and confirm:
- The "See project LICENSE file" line appears at the top
- The table renders with all 26 rows
- Links in the "Project" column are clickable
- The table is readable and properly formatted

- [ ] **Step 4: Commit**

```bash
git add pages/about.py
git commit -m "feat: add third-party license attribution to about page"
```
