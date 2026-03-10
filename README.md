# Modular Digital Methodologies Toolkit (MDMT)

A comprehensive suite of digital humanities and research tools designed to streamline text analysis, document processing, and data extraction workflows.

## Overview

MDMT is a desktop application that provides researchers, scholars, and digital humanists with a variety of specialized tools for working with text-based documents. It offers a modular approach, allowing users to perform tasks ranging from optical character recognition to language translation and advanced text analysis, all through a unified web-based interface running in a native window.

## Features

### Document Processing
- **OCR (Optical Character Recognition)**: Convert image-based PDFs to searchable, selectable text using Tesseract OCR with support for 100+ languages
- **Audio Transcription**: Convert speech in audio files to text using OpenAI's Whisper model
- **Language Translation**: Translate documents between multiple languages using Google Translate

### Text Analysis
- **Advanced Keyword Search**: Find and analyze keyword patterns across document collections with visualization
- **Named Entity Recognition**: Identify and extract people, organizations, locations, and other named entities
- **Relationship Extraction**: Discover connections between entities in texts and visualize network graphs
- **Co-Word Analysis**: Generate word co-occurrence networks to reveal conceptual relationships

### AI Integration
- **Retrieval-Augmented Generation (RAG)**: Chat with your documents using an AI assistant powered by Qwen 3.5 models
  - **Note (2026-03-10):** RAG is currently non-functional. The Qwen 3.5 model architecture (`qwen35`) is not yet supported by the latest `llama-cpp-python` release on PyPI (0.3.16). This will be resolved once an updated release is published. See [llama.cpp #19468](https://github.com/ggml-org/llama.cpp/pull/19468).

## Installation

### Prerequisites
- Python 3.12 or newer
- Tesseract OCR (system package)
- Required Python dependencies (see `requirements.txt`)

### Setup
1. Clone this repository
2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```

## Usage

Launch MDMT with `python app.py`. The application opens in a native desktop window with a sidebar for navigation between modules:

1. **OCR**: Process PDFs to make them searchable with text selection
2. **Audio Transcription**: Convert audio files to text transcriptions
3. **Translation**: Translate documents between languages
4. **Advanced Keyword Search**: Find and analyze keywords with context
5. **Named Entity Recognition**: Extract named entities from documents
6. **Relationship Extraction**: Identify entity relationships and generate network graphs
7. **Co-Word Analysis**: Generate word co-occurrence networks
8. **RAG Chat**: Query your document collection using a local LLM
9. **Downloads**: Manage optional assets (Tesseract languages, Whisper models, NLTK data, LLM models)

Optional assets (language models, NLTK data, Tesseract language files) are downloaded on demand via the Downloads page. Large ML models are not bundled with the application.

## TODO

- **About page**: Add all required third-party licenses.
- **Advanced Keywords UI**: Redesign the Advanced Keywords module interface — the large keyword textboxes make the page difficult to navigate.
- **Verify cross-platform capability**: Ensure the program runs on Mac, Windows, and Linux.
- **UI Theme Redesign**: Move away from the flat, minimal (basic) look currently used? At a minimum, offer a dark and light mode.

## Dependencies

Major dependencies include:
- `nicegui` + `pywebview`: Web-based UI in a native desktop window
- `ocrmypdf`: OCR functionality
- `openai-whisper`: Audio transcription
- `transformers`: Named entity recognition
- `nltk` + `networkx`: NLP and graph analysis
- `langchain`: RAG implementation
- `pandas`: Data manipulation
- `matplotlib`: Data visualization
- `pypdf`: PDF text extraction

See `requirements.txt` for a complete list.

## Building

To build a standalone executable:
```
pip install pyinstaller
pyinstaller mdmt.spec
```

The spec file uses `--onedir` mode to avoid multi-GB extraction on each launch.

## License

This project uses several open-source libraries, each with their own licenses. See the Help/About page within the application for details.

## Contact

Software by James C. Caldwell
Email: James.Caldwell.000@gmail.com
