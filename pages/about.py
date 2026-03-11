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

    # --- Getting Started ---
    with ui.card().classes("w-full mt-4"):
        ui.label("Getting Started").classes("text-h5")
        ui.markdown("""
1. Use the **sidebar** to navigate between modules.
2. Some modules require downloading models or language data first \u2014 visit the
   **Downloads** page to manage these.
3. Each module has its own input/output configuration. Browse for directories
   using the folder buttons, adjust settings, then click the action button to run.
        """)

    # --- Module Help ---
    ui.label("Module Reference").classes("text-h5 q-mt-lg")
    ui.label("Click a module name to expand its usage guide.").classes("text-caption text-grey")

    # OCR
    with ui.expansion("OCR Processing", icon="document_scanner").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Converts scanned or image-based PDFs into text-searchable PDFs
using Tesseract OCR. Can also optionally extract the recognized text to separate
`.txt` files.

**How to use:**
1. Select an **Input Directory** containing PDF files.
2. Select a different **Output Directory** for the processed files.
3. Choose the **Languages** present in your documents. Selecting the correct
   languages significantly improves recognition accuracy. If you need a language
   that isn't listed, download it from the **Downloads** page.
4. Adjust options as needed (see below), then click **Run OCR**.

**Options:**
- **Deskew** \u2014 Straightens pages that were scanned at a slight angle. Cannot be
  used together with Redo OCR.
- **Rotate Pages** \u2014 Automatically detects and corrects page rotation (e.g. pages
  scanned upside-down). When enabled, you can set the **Rotation Sensitivity**:
  High catches subtle rotations, Low only corrects obvious ones.
- **Redo OCR** \u2014 Strips any existing OCR text layer and re-runs recognition from
  scratch. Useful if a previous OCR pass produced poor results. Cannot be used
  together with Deskew.
- **PDF/A Output** \u2014 Produces PDF/A-compliant files, an archival format suitable
  for long-term preservation.
- **Extract Text** \u2014 Saves the recognized text to a `.txt` file alongside each
  output PDF.

**Tips:**
- Always select every language that appears in your documents. Mixed-language
  documents (e.g. English with French quotations) need both languages selected.
- For best results, ensure scans are at least 300 DPI.
        """)

    # Audio Transcription
    with ui.expansion("Audio Transcription", icon="mic").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Converts speech in audio files to text using OpenAI's Whisper
speech recognition model. Outputs a `.txt` transcript for each audio file.

**How to use:**
1. Select a directory containing audio files (supports `.mp3`, `.wav`, `.m4a`,
   `.flac`, `.ogg`, and other common formats).
2. Choose a **Whisper Model** size.
3. Click **Transcribe**.

**Model sizes:**
- **tiny** (~75 MB) \u2014 Fastest, lowest accuracy. Good for quick drafts or testing.
- **base** (~142 MB) \u2014 Fast with improved accuracy over tiny. Suitable for clear,
  well-recorded audio.
- **small** (~466 MB) \u2014 Balanced speed and accuracy. Good for most use cases.
- **medium** (~1.5 GB) \u2014 Best accuracy, slowest. Recommended for difficult audio,
  background noise, accents, or non-English languages.

Larger models require more RAM and processing time. If you haven't downloaded a
model yet, visit the **Downloads** page. The model will be loaded into memory
during transcription.

**Tips:**
- Start with **tiny** to verify your files work, then switch to a larger model
  for final transcriptions.
- For non-English audio, **small** or **medium** will produce significantly better
  results.
        """)

    # Translation
    with ui.expansion("Translation", icon="translate").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Translates PDF documents from one language to another using
Google Translate. Produces translated PDF copies alongside the originals.

**How to use:**
1. Select an **Input Directory** containing the PDF files to translate.
2. Choose the source language (or leave on **Auto-detect**) and the target
   language.
3. Optionally change the **Output Suffix** (appended to each translated filename).
4. Click **Translate**.

**Important \u2014 PDFs must be text-searchable:**
The translation module works by extracting text from PDFs. If your PDFs are
scanned images without an embedded text layer, they cannot be translated. Run
the **OCR module** first to add a text layer, then translate the OCR'd output.

**Tips:**
- Auto-detect works well for single-language documents. For mixed-language
  documents, specifying the source language may improve results.
- Very large PDFs are split into chunks automatically to stay within translation
  limits.
        """)

    # Advanced Keyword Search
    with ui.expansion("Advanced Keyword Search", icon="search").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Searches a collection of PDF documents for specified keywords
and produces a detailed report with context snippets, frequency counts, and
charts.

**How to use:**
1. Select a **PDF Input Directory** and a separate **Output Directory** for results.
2. Set the **Context Length** \u2014 the number of words shown before and after each
   keyword match (default: 5).
3. Enter your **Keywords**, one per line. These are the terms to search for.
4. Optionally configure filters (see below).
5. Click **Analyze**.

**Filters:**
- **Basic Filter (letters & numbers only)** \u2014 When enabled, strips all characters
  except letters and numbers from the extracted PDF text before searching. This
  is useful for cleaning up OCR artifacts, stray punctuation, or special
  characters that might prevent keyword matches.
- **Filter words** (textarea below) \u2014 Words to exclude from results. If a keyword
  match's surrounding context contains any of these filter words, that match is
  removed from the output. Enter one filter word per line. Useful for eliminating
  false positives (e.g. filtering out "table of contents" matches).

**Loading from files:**
Instead of typing keywords and filters manually, you can load them from text
files using the expandable "Or load from files..." section. The files should
contain one keyword or filter word per line.

**Tips:**
- Use short, specific keywords for more relevant results.
- The output directory will contain a spreadsheet and charts summarizing the
  keyword analysis.
        """)

    # Named Entity Recognition
    with ui.expansion("Named Entity Recognition", icon="person_search").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Identifies and extracts named entities \u2014 people, organizations,
locations, dates, and other proper nouns \u2014 from your documents using a
HuggingFace BERT model.

**How to use:**
1. Select an **Input Directory** containing text or PDF files.
2. Click **Run NER**.
3. Results are saved in the input directory.

**Note:** On first run, the NER model (~1.3 GB) will be downloaded automatically.
This is a one-time download.

**Tips:**
- Works best on clean, well-structured text. Running OCR first on scanned
  documents will improve entity detection.
- The model recognizes entities in English. For other languages, results may
  vary.
        """)

    # Relationship Extraction
    with ui.expansion("Relationship Extraction", icon="hub").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Discovers connections between named entities (people,
organizations, places, etc.) found in your documents. Can produce a network
graph visualizing these relationships.

**How to use:**
1. Select an **Input Directory** containing your documents.
2. Choose which **Entity Types** to look for (e.g. PERSON, ORGANIZATION, GPE).
3. Configure options:
   - **Extract text from PDFs** \u2014 Enable this to extract raw text from PDF files
     before processing. Leave unchecked if your input directory already contains
     plain text (`.txt`) files.
   - **Generate network graph** \u2014 Produces an interactive HTML graph showing
     entity connections.
4. Click **Extract Relationships**.

**Entity types explained:**
- **PERSON** \u2014 People's names
- **ORGANIZATION** \u2014 Companies, agencies, institutions
- **GPE** \u2014 Geopolitical entities (countries, cities, states)
- **LOCATION** \u2014 Non-GPE locations (mountains, rivers, regions)
- **FACILITY** \u2014 Buildings, airports, highways
- **DATE / TIME / MONEY / PERCENT** \u2014 Numeric and temporal entities

**Tips:**
- NLTK data packages are required. They will download automatically on first
  run, or you can pre-download them from the **Downloads** page.
- Start with the default entity types (PERSON, ORGANIZATION, GPE) for the most
  useful relationship maps.
        """)

    # Co-Word Analysis
    with ui.expansion("Co-Word Analysis", icon="share").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Analyzes how frequently words appear together in your documents
to reveal conceptual relationships. Produces a co-occurrence network and a
summary report.

**How to use:**
1. Select an **Input Directory** containing text or PDF files.
2. Click **Run Analysis**.
3. Results, including an HTML summary report, are saved in the input directory.

**Tips:**
- Like Relationship Extraction, this module requires NLTK data packages.
  Download them from the **Downloads** page if they haven't been installed yet.
- Works best with larger document collections where word co-occurrence patterns
  are meaningful.
        """)

    # RAG Chat
    with ui.expansion("RAG Chat", icon="smart_toy").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Lets you ask questions about your documents using a local
Qwen AI model. The system indexes your documents and uses Retrieval-Augmented
Generation (RAG) to find relevant passages and generate answers.

**How to use:**
1. Select a **Documents Directory** containing the files to index.
2. Select a **Model File** — a Qwen 3.5 `.gguf` model. If you don't have one,
   download it from the **Downloads** page.
3. Optionally adjust **Context Length** and **Thinking Mode** settings.
4. Click **Initialize RAG** to load the model and index your documents.
5. Once initialized, type questions in the chat box and press Enter or click
   Send.

**Tips:**
- MDMT auto-detects your hardware and recommends the best model size.
- Initialization can take a minute or more depending on the number of documents
  and model size.
- The AI will cite which documents (and pages) it used to answer your question.
- Enable **Thinking Mode** for more thorough reasoning on complex questions.
- For best results, use focused document collections rather than very large
  mixed archives.
        """)

    # License
    with ui.expansion("License", icon="gavel").classes("w-full mt-2"):
        ui.markdown("See project LICENSE file for full license terms.")
        ui.markdown("""
| Library | License | Project |
|---|---|---|
| BeautifulSoup4 | MIT | [crummy.com](https://www.crummy.com/software/BeautifulSoup/) |
| docx2txt | MIT | [GitHub](https://github.com/ankushshah89/python-docx2txt) |
| FAISS | MIT | [GitHub](https://github.com/facebookresearch/faiss) |
| future | MIT | [GitHub](https://github.com/PythonCharmers/python-future) |
| googletrans | MIT | [GitHub](https://github.com/ssut/py-googletrans) |
| Hugging Face Hub | Apache-2.0 | [GitHub](https://github.com/huggingface/huggingface_hub) |
| LangChain (core, community, huggingface, text-splitters) | MIT | [GitHub](https://github.com/langchain-ai/langchain) |
| llama-cpp-python (fork) | MIT | [GitHub](https://github.com/JamePeng/llama-cpp-python) |
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
