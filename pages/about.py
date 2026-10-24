"""Help / About / License page."""
from nicegui import ui

from pages.components import page_header, section

from version import __version__


def about_page():
    page_header("Help / About", "Modular Digital Methodologies Toolkit")

    with section("About MDMT"):
        ui.markdown(f"""
**Version:** {__version__}

**Author:** James C. Caldwell

MDMT is a modular application for digital humanities and research workflows,
providing tools for text analysis, document processing, and data extraction.
        """)

        def open_logs():
            from common.logs import get_log_dir
            from common.opener import open_external
            open_external(get_log_dir())

        ui.button("Open log folder", icon="folder_open", on_click=open_logs).props("flat dense")

    # --- Getting Started ---
    with section("Getting started"):
        ui.markdown("""
1. Use the **sidebar** to move between tools.
2. Some tools require downloading models or language data first \u2014 visit the
   **Downloads** page to manage these.
3. Each tool remembers its settings. Choose folders with the folder button next
   to each field, then click the tool's main button. Work continues in the
   background if you open another page; the sidebar lists what is running, and
   a running job can be cancelled between files.
        """)

    # --- Module Help ---
    ui.label("Tool reference").classes("text-subtitle1 text-weight-medium q-mt-md")
    ui.label("Click a tool to expand its guide.").classes("text-caption text-grey")

    # OCR
    with ui.expansion("OCR", icon="document_scanner").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Converts scanned or image-based PDFs into text-searchable PDFs
using Tesseract OCR. Can also optionally extract the recognized text to separate
`.txt` files.

**How to use:**
1. Choose an **Input folder** containing PDF files (sub-folders are included).
2. Choose a different **Output folder**, not inside the input folder (the next
   run would process the outputs again).
3. Choose the **Languages** present in your documents. Selecting the correct
   languages significantly improves recognition accuracy. If you need a language
   that isn't listed, download it from the **Downloads** page.
4. Adjust options as needed (see below), then click **Run OCR**.

**Options:**
- **Deskew** \u2014 Straightens pages that were scanned at a slight angle. Cannot be
  used together with Redo OCR.
- **Rotate pages** \u2014 Automatically detects and corrects page rotation (e.g. pages
  scanned upside-down). Uses the `osd` data file, installed by default. When enabled, you can set the **Rotation sensitivity**:
  High catches subtle rotations, Low only corrects obvious ones.
- **Redo OCR** \u2014 Strips any existing OCR text layer and re-runs recognition from
  scratch. Useful if a previous OCR pass produced poor results. Cannot be used
  together with Deskew.
- **PDF/A output** \u2014 Produces PDF/A-compliant files, an archival format suitable
  for long-term preservation. Requires [Ghostscript](https://ghostscript.com/releases/gsdnld.html),
  which MDMT does not bundle; the option is disabled until Ghostscript is installed.
- **Extract text (.txt)** \u2014 Saves the recognized text to a `.txt` file alongside each
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
speech recognition model, run offline with faster-whisper. Outputs a `.txt`
transcript for each audio file.

**How to use:**
1. Select a directory containing audio files (`.mp3`, `.wav`, `.m4a`, `.flac`,
   `.ogg`, `.webm`, `.mp4`, `.mpeg`, `.mpga`).
2. Choose a **Whisper model** size.
3. Leave **Skip silence** on for long recordings (see below).
4. Click **Transcribe**.

**Skip silence (voice activity filter):** On by default. It removes stretches
without speech before transcription, which avoids Whisper's tendency to invent
repeated phrases over silence, music or tape hiss in long archival recordings,
and speeds things up. Turn it off if very quiet speech is being dropped.

Transcription runs on the CPU (int8), on every platform.

**Model sizes:**
- **tiny** (~78 MB) \u2014 Fastest, lowest accuracy. Good for quick drafts or testing.
- **base** (~148 MB) \u2014 Fast with improved accuracy over tiny. Suitable for clear,
  well-recorded audio.
- **small** (~486 MB) \u2014 Balanced speed and accuracy. Good for most use cases.
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
**What it does:** Translates text and PDF documents offline with Argos
Translate models (CTranslate2). Your documents never leave your computer.
Each translated document is saved next to the original as
`name_translated.txt`.

**How to use:**
1. Choose an **Input folder** containing `.txt` or text-searchable `.pdf` files.
2. Choose the source language (or **Auto-detect**) and the target language.
3. If the page says a model is needed, click **Download** (models are 65\u2013285 MB
   each, one per direction; you can also manage them on the **Downloads** page).
4. Optionally change the **Output suffix**, then click **Translate**.

**Languages:** about 50 languages to and from English. Other pairs (e.g.
French \u2192 German) are translated through English, which compounds errors.

**Important \u2014 PDFs must be text-searchable:**
The translation module works by extracting text from PDFs. If your PDFs are
scanned images without an embedded text layer, they cannot be translated. Run
the **OCR module** first to add a text layer, then translate the OCR'd output.

        """)
        from Translation.offline_translation import ARGOS_DISCLAIMER
        ui.markdown("**About the models:** " + ARGOS_DISCLAIMER)
        ui.markdown("""
**Tips:**
- Offline models are smaller than online services and can be weaker for some
  language pairs. Historical terms, place names and archaic spelling are often
  mistranslated, so use the output as a reading aid, not a final translation.
- Auto-detect picks among the languages you have models for. For short or
  mixed-language documents, choose the source language yourself.
- Files whose names already end with the output suffix are skipped, so running
  the same folder again does not translate the translations.
        """)

    # Advanced Keyword Search
    with ui.expansion("Keyword Search", icon="search").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Searches a collection of PDF documents for specified keywords
and produces a detailed report with context snippets, frequency counts, and
charts.

**How to use:**
1. Choose a **PDF folder** and a separate **Output folder** for the results.
2. Enter your **Keywords**, one per line.
3. Set the **Context length**: the total number of words saved around each
   match, half before it and half after (default: 5).
4. Optionally set filters (see below).
5. Click **Search**.

**Filters** (applied to the text before searching; the first that applies wins):
- **Basic filter** keeps only letters, digits and spaces (including line
  breaks), removing punctuation, symbols and OCR noise. Letters of every
  language are kept with their accents: é, ł, ß, Москва, 北京.
- Otherwise, every **character** listed in the filter file, or typed in the
  filter box, is removed from the text: entering `#*` deletes every `#` and `*`.
  This cleans up OCR noise that splits words.

**Loading from files:**
Instead of typing them, keywords (one per line) and filter characters can be
loaded from text files in the "Or load keywords and filters from files" section.

**Tips:**
- Use short, specific keywords for more relevant results.
- The output directory will contain a spreadsheet and charts summarizing the
  keyword analysis.
        """)

    # Named Entity Recognition
    with ui.expansion("Named Entities", icon="person_search").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Identifies people (PER), organizations (ORG), places (LOC)
and dates (DATE) in your documents with a multilingual BERT model that runs
offline (ONNX Runtime). Trained on news text in Arabic, Chinese, Dutch,
English, French, German, Italian, Latvian, Portuguese and Spanish; other
languages may work less well.

**How to use:**
1. Choose an **Input folder** containing text or PDF files.
2. Click **Find entities**.
3. Results are saved in the input directory: a summary table and, for each
   document, a copy with the entities highlighted.

**Note:** The model (~182 MB) downloads on first use, or in advance from the
**Downloads** page.

**Tips:**
- Works best on clean, well-structured text. Running OCR first on scanned
  documents will improve entity detection.
- Historical spellings and very old texts are harder for any modern model;
  spot-check the highlighted files.
        """)

    # Relationship Extraction
    with ui.expansion("Relationships", icon="hub").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Finds pairs of named entities that appear in the same
sentence, records the words connecting them, and can draw a network graph of
these connections.

**How to use:**
1. Choose an **Input folder** containing your documents.
2. Choose which **Entity types** to include.
3. Configure options:
   - **Save text extracted from PDFs** \u2014 Also saves the text of each PDF as
     `<name>_text.txt`; later runs do not process these files again.
   - **Draw network graphs** \u2014 Saves network images (PNG) of all entities
     and of each entity type.
4. Click **Extract Relationships**. Results go to `relationships.csv`
   (Excel-friendly) in the input directory.

**Entity types** (from the NER model):
- **PER** \u2014 people
- **ORG** \u2014 organizations and institutions
- **LOC** \u2014 places: countries, cities, regions, landmarks
- **DATE** \u2014 dates

**The Relationship column** contains the words between the two entities in the
sentence (up to eight, without other entities' names), or "is connected to"
when they are adjacent. Versions before 2.1 used NLTK's entity types
(PERSON, ORGANIZATION, GPE, ...) and kept only the verbs.

**Tips:**
- The NER model (~182 MB) downloads on first use, or from the **Downloads** page.
- Start with PER, ORG and LOC for the most useful relationship maps.
        """)

    # Co-Word Analysis
    with ui.expansion("Co-Words", icon="grain").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Analyzes how frequently words appear together in your documents
to reveal conceptual relationships. Produces a co-occurrence network and a
summary report.

**How to use:**
1. Choose an **Input folder** containing text or PDF files.
2. Choose the **Stopword list** for the documents' language, and optionally add
   your own words to ignore.
3. Click **Run analysis**.
4. Results, including an HTML summary report, are saved in the input directory.

**Stopword lists:** Snowball lists (17 languages) contain only function words.
For other languages MDMT uses the broader stopwords-iso lists, marked
"extended", which may also remove some content words.

**Tips:**
- Words in any script are counted; Chinese and Japanese are counted per
  character, because MDMT does not segment text written without spaces.
- Works best with larger document collections where word co-occurrence patterns
  are meaningful.
        """)

    # RAGBot
    with ui.expansion("RAGBot", icon="smart_toy").classes("w-full mt-2"):
        ui.markdown("""
**What it does:** Lets you ask questions about a folder of documents using a
local Qwen model. MDMT indexes the documents, finds the passages most relevant
to each question (keyword search and multilingual embeddings, optionally
reranked), and asks the model to answer from those passages only, citing them.
Nothing leaves your computer.

**How to use:**
1. Choose a **Documents folder** (TXT, PDF, Markdown, HTML, CSV, JSON, DOCX).
2. Choose a **Model file**, a Qwen 3.5 `.gguf` model from the **Downloads** page.
3. Optionally adjust **Context length**, **Thinking mode** and **Rerank passages**.
4. Click **Start**. The first start downloads the retrieval models (about
   135 MB, plus 588 MB for the reranker) and indexes the folder; later starts
   only re-read files that changed.
5. Ask a question. The answer streams in; **Stop** ends it early.

**Tips:**
- Numbers such as [1] in an answer are citations. Click a source chip to read
  the passage and open its file.
- Follow-up questions can refer to earlier ones ("What did it carry?");
  **New conversation** starts afresh.
- If the documents do not contain the answer, the model says so rather than
  guessing. Answers can still be wrong: check the cited passages.
- **Re-index** picks up files added or edited while the chat is open.
- **Rerank passages** improves accuracy but is slower on older computers.
- **Thinking mode** lets the model reason first: slower, sometimes better on
  complex questions.
- Ask in the language of your documents. A question in another language
  (English about a French text, say) often misses the right passages.
- Two chat models are offered. **2B** (1.28 GB) suits any computer from the
  last few years and runs well without a GPU.
  **4B** (2.74 GB) is somewhat more accurate but needs a GPU to be quick;
  MDMT recommends it when it finds one.
        """)

    # License
    with ui.expansion("Licenses", icon="gavel").classes("w-full mt-2"):
        ui.markdown("MDMT is MIT-licensed -- see the project's `LICENSE` file. "
                    "License texts for bundled third-party libraries are in "
                    "`THIRD_PARTY_LICENSES`.")
        ui.markdown("""
| Library | License | Project |
|---|---|---|
| PyAV | BSD-3-Clause | [GitHub](https://github.com/PyAV-Org/PyAV) |
| FFmpeg (audio decoders only, built without GPL components; see `THIRD_PARTY_LICENSES`) | LGPL-2.1-or-later | [ffmpeg.org](https://ffmpeg.org/) |
| CTranslate2 | MIT | [GitHub](https://github.com/OpenNMT/CTranslate2) |
| faster-whisper (includes Silero VAD model) | MIT | [GitHub](https://github.com/SYSTRAN/faster-whisper) |
| Hugging Face Hub | Apache-2.0 | [GitHub](https://github.com/huggingface/huggingface_hub) |
| Jinja2 | BSD-3-Clause | [GitHub](https://github.com/pallets/jinja) |
| llama-cpp-python (fork) | MIT | [GitHub](https://github.com/JamePeng/llama-cpp-python) |
| Matplotlib | PSF-2.0 | [GitHub](https://github.com/matplotlib/matplotlib) |
| NetworkX | BSD-3-Clause | [GitHub](https://github.com/networkx/networkx) |
| NiceGUI | MIT | [GitHub](https://github.com/zauberzeug/nicegui) |
| OCRmyPDF | MPL-2.0 | [GitHub](https://github.com/ocrmypdf/OCRmyPDF) |
| ONNX Runtime | MIT | [GitHub](https://github.com/microsoft/onnxruntime) |
| platformdirs | MIT | [GitHub](https://github.com/tox-dev/platformdirs) |
| Snowball stopword lists (bundled data) | BSD-3-Clause | [snowballstem.org](https://snowballstem.org/) |
| stopwords-iso (bundled data) | MIT | [GitHub](https://github.com/stopwords-iso/stopwords-iso) |
| psutil | BSD-3-Clause | [GitHub](https://github.com/giampaolo/psutil) |
| py3langid | BSD-3-Clause | [GitHub](https://github.com/adbar/py3langid) |
| pypdfium2 | Apache-2.0 / BSD-3-Clause | [GitHub](https://github.com/pypdfium2-team/pypdfium2) |
| sacremoses | MIT | [GitHub](https://github.com/hplt-project/sacremoses) |
| SentencePiece | Apache-2.0 | [GitHub](https://github.com/google/sentencepiece) |
| pywebview (Windows and macOS) | BSD-3-Clause | [GitHub](https://github.com/r0x0r/pywebview) |
| Tesseract OCR (and bundled tessdata `eng`, `osd`) | Apache-2.0 | [GitHub](https://github.com/tesseract-ocr/tesseract) |
| Tokenizers (Hugging Face) | Apache-2.0 | [GitHub](https://github.com/huggingface/tokenizers) |
""")
        ui.markdown("""
**Downloadable models** (never bundled; fetched on demand from the Downloads page):

| Model | License | Source |
|---|---|---|
| Whisper tiny/base/small/medium, CTranslate2 conversions | MIT | [Systran on Hugging Face](https://huggingface.co/Systran) |
| Tesseract language data (`tessdata`) | Apache-2.0 | [GitHub](https://github.com/tesseract-ocr/tessdata) |
| Qwen 3.5 GGUF (2B / 4B) | Apache-2.0 | [unsloth on Hugging Face](https://huggingface.co/unsloth) |
| Argos Translate models (one per language pair) | Varies by model: 59 of 100 state CC-BY 4.0 (derived from OPUS-MT); the rest cite their OPUS training data or state no license. See each model's README. | [Argos Translate](https://github.com/argosopentech/argos-translate) |
| multilingual-e5-small, ONNX export (RAG retrieval) | MIT | [Hugging Face](https://huggingface.co/intfloat/multilingual-e5-small) |
| bge-reranker-v2-m3, ONNX export (RAG reranking, optional) | Apache-2.0 | [Hugging Face](https://huggingface.co/BAAI/bge-reranker-v2-m3) |
| bert-base-multilingual-cased-ner-hrl, uint8 ONNX export (NER, Relationships) | AFL-3.0 | [Hugging Face](https://huggingface.co/Davlan/bert-base-multilingual-cased-ner-hrl) |
""")
