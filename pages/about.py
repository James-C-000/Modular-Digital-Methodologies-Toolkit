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
