"""Reading the text of input documents, shared by every tool that takes .txt files.

Plain-text files are not always UTF-8: older Windows programs (Notepad before
Windows 10, Word's "Plain Text" export) write Windows-1252, and Notepad's
"Unicode" is UTF-16.  Reading those as strict UTF-8 fails, so every tool
decodes the same way.
"""

_UTF_BOMS = ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
             (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"))


def _utf16_without_bom(raw: bytes) -> str | None:
    """*raw* decoded as UTF-16 if its NUL bytes say so, else None.

    Text files contain no NUL bytes, but UTF-16 without a byte order mark has
    one in every other byte wherever the text is ASCII.
    """
    even, odd = raw[0::2].count(0), raw[1::2].count(0)
    if max(even, odd) < len(raw) // 4:
        return None
    try:
        return raw.decode("utf-16-be" if even > odd else "utf-16-le")
    except UnicodeDecodeError:
        return None


def read_text(path: str) -> str:
    """Text of a plain-text file: UTF-8 (with or without a BOM), UTF-16 or UTF-32, else
    Windows-1252, else Latin-1.

    Latin-1 decodes any bytes, so this only raises if the file cannot be read.
    """
    with open(path, "rb") as f:
        raw = f.read()
    for bom, encoding in _UTF_BOMS:
        if raw.startswith(bom):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                break
    # Before UTF-8, which also accepts NUL bytes, and Windows-1252, which decodes them into nonsense.
    if b"\x00" in raw:
        text = _utf16_without_bom(raw)
        if text is not None:
            return text
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


SAVED_TEXT_SUFFIX = "_text.txt"


def _comparable_text(text: str) -> str:
    # Saved on Windows with CRLF line ends, or by an MDMT that kept PDFium's line-end hyphen marker.
    return text.replace("\r\n", "\n").replace("\x02", "-\n")


class SavedTextCheck:
    """Recognizes the "<name>_text.txt" that Relationships saves next to "<name>.pdf".

    Remember the text of each PDF as it is read; a "<name>_text.txt" read
    later (it sorts after "<name>.pdf") holding the same text is that saved
    copy, which would otherwise be analysed twice.  A file of that name with
    other text is the user's own.
    """

    def __init__(self):
        self._pdf_texts = {}

    def remember(self, path: str, text: str):
        if path.lower().endswith(".pdf"):
            self._pdf_texts[path[:-len(".pdf")].casefold()] = _comparable_text(text)

    def is_saved_text(self, path: str, text: str) -> bool:
        if not path.lower().endswith(SAVED_TEXT_SUFFIX):
            return False
        saved = self._pdf_texts.get(path[:-len(SAVED_TEXT_SUFFIX)].casefold())
        return saved is not None and saved == _comparable_text(text)
