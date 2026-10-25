"""Reading the text of input documents, shared by every tool that takes .txt files.

Plain-text files are not always UTF-8: older Windows programs (Notepad before
Windows 10, Word's "Plain Text" export) write Windows-1252.  Reading those as
strict UTF-8 fails, so every tool decodes the same way.
"""


def read_text(path: str) -> str:
    """Text of a plain-text file: UTF-8 (with or without a BOM), else Windows-1252, else Latin-1.

    Latin-1 decodes any bytes, so this only raises if the file cannot be read.
    """
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def document_text(path: str) -> str:
    """Text of a .pdf (its text layer; '' for scanned PDFs) or of a plain-text file."""
    from common.pdf_text import extract_text  # pypdfium2, only when a PDF needs it
    return extract_text(path) if path.lower().endswith(".pdf") else read_text(path)
