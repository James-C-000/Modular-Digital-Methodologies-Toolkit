# Modular Digital Methodologies Toolkit (MDMT)

A comprehensive suite of digital humanities and research tools designed to streamline text analysis, document processing, and data extraction workflows.

## Overview

MDMT is a desktop application that provides researchers, scholars, and digital humanists with a variety of specialized tools for working with text-based documents. It offers a modular approach, allowing users to perform tasks ranging from optical character recognition to language translation and advanced text analysis, all through a unified interface.

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
- **Retrieval-Augmented Generation (RAG)**: Chat with your documents using an AI assistant powered by Llama models

## Installation

### Prerequisites
- Python 3.8 or newer
- Required dependencies (see `requirements.txt`)

### Setup
1. Clone this repository
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python MDMT_Launcher.py
   ```

### Pre-built Binaries
Pre-built binaries for Windows, macOS, and Linux will be made available in the releases section.

## Usage

Launch MDMT using `MDMT_Launcher.py` to access the main interface, which provides buttons for each module:

1. **OCR**: Process PDFs to make them searchable with text selection
2. **Audio Transcription**: Convert audio files to text transcriptions
3. **Translation**: Translate documents between languages
4. **RAG Chatbot**: Query your document collection using AI
5. **Advanced Keyword Search**: Find and analyze keywords with visualizations
6. **Named Entity Recognition**: Extract named entities from documents
7. **Relationship Extraction**: Identify entity relationships
8. **Co-Word Analysis**: Generate word co-occurrence networks

Each module has its own interface with specific options and settings.

## Documentation

Each tool includes in-app help documentation accessible through the Help menu. The documentation covers:
- Input/output requirements
- Available options and settings
- Processing details
- Output formats

## Dependencies

Major dependencies include:
- `matplotlib`: For data visualization
- `ocrmypdf`: For OCR functionality
- `pygubu`: For the user interface
- `pandas`: For data manipulation
- `nltk`: For natural language processing
- `transformers`: For NER and other NLP tasks
- `whisper`: For audio transcription
- `langchain`: For RAG implementation
- `pypdf`: For PDF processing

See `requirements.txt` for a complete list.
Todo: make sure requirements.txt has complete coverage

## Development

### Project Structure
- Main modules are organized in subdirectories by function
- UI files (`*.ui`) define the interface layouts
- Window classes (`*Window.py`) handle UI logic
- Core functionality is implemented in dedicated modules

### Building
To build executable versions:
```
pip install pyinstaller
pyinstaller MDMT_Launcher.spec
```

## License

This project uses several open-source libraries, each with their own licenses:
- Matplotlib: Matplotlib Development Team (License included in the application)
- pdftotext: Jason Alan Palmer (MIT License)
- pygubu: Alejandro Autalán (MIT License)

Todo: add complete list of licenses 

## Contact

Software by James C. Caldwell  
Email: James.Caldwell.000@gmail.com
