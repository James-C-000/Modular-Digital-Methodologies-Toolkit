# Licenses Section Design

## Summary

Replace the minimal license reference in `pages/about.py` with a comprehensive alphabetical table crediting all runtime dependencies. Each entry includes the library name, license type (SPDX identifier), and a project link.

## Current State

The License expansion in the about page contains only:
> "See project LICENSE file for full license terms."

## Design

### Scope
- Runtime dependencies only (no dev/test tools like pytest)
- Includes both Python packages and bundled external programs (Tesseract OCR)

### Format
- Each entry: **Name | License | Link**
- Organized as a single alphabetical flat list
- Related packages consolidated (e.g., LangChain variants, PyQt6 variants)

### Content

The following 26 entries will appear in a NiceGUI markdown table:

| Library | License | URL |
|---|---|---|
| BeautifulSoup4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| docx2txt | MIT | https://github.com/ankushshah89/python-docx2txt |
| FAISS | MIT AND BSD-3-Clause | https://github.com/facebookresearch/faiss |
| future | MIT | https://github.com/PythonCharmers/python-future |
| googletrans | MIT | https://github.com/ssut/py-googletrans |
| Hugging Face Hub | Apache-2.0 | https://github.com/huggingface/huggingface_hub |
| LangChain (core, community, huggingface, text-splitters) | MIT | https://github.com/langchain-ai/langchain |
| llama-cpp-python | MIT | https://github.com/abetlen/llama-cpp-python |
| Matplotlib | PSF-2.0 | https://github.com/matplotlib/matplotlib |
| NetworkX | BSD-3-Clause | https://github.com/networkx/networkx |
| NiceGUI | MIT | https://github.com/zauberzeug/nicegui |
| NLTK | Apache-2.0 | https://github.com/nltk/nltk |
| OCRmyPDF | MPL-2.0 | https://github.com/ocrmypdf/OCRmyPDF |
| OpenAI Whisper | MIT | https://github.com/openai/whisper |
| openpyxl | MIT | https://openpyxl.readthedocs.io/ |
| pandas | BSD-3-Clause | https://github.com/pandas-dev/pandas |
| platformdirs | MIT | https://github.com/tox-dev/platformdirs |
| psutil | BSD-3-Clause | https://github.com/giampaolo/psutil |
| pypdf | BSD-3-Clause | https://github.com/py-pdf/pypdf |
| PyQt6 / PyQt6-WebEngine | GPL-3.0-only | https://riverbankcomputing.com/software/pyqt/ |
| pywebview | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| QtPy | MIT | https://github.com/spyder-ide/qtpy |
| Requests | Apache-2.0 | https://github.com/psf/requests |
| Sentence-Transformers | Apache-2.0 | https://github.com/UKPLab/sentence-transformers |
| Tesseract OCR | Apache-2.0 | https://github.com/tesseract-ocr/tesseract |
| Transformers (HuggingFace) | Apache-2.0 | https://github.com/huggingface/transformers |

### Location

`pages/about.py` — inside the existing `ui.expansion("License", icon="gavel")` block. The current "See project LICENSE file" line is kept as a header, with the dependency table appended below it.

### Implementation Notes

- The table is rendered via `ui.markdown()` — NiceGUI supports markdown tables natively
- URLs must be formatted as proper markdown links (e.g., `[project](https://url)`) since NiceGUI's markdown renderer does not auto-link bare URLs
- No new files or modules needed; this is a single edit to `pages/about.py`
- Note: the existing "See project LICENSE file" line references a LICENSE file that does not yet exist in the repo — this should be addressed separately
