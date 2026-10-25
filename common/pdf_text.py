"""PDF text extraction shared by every module (pypdfium2, already required by ocrmypdf).

Returns text per page so callers can report page numbers.  Scanned PDFs
without a text layer yield empty strings; run them through OCR first.

PDFium replaces a hyphen (or soft hyphen) that ends a line with "\\x02" and
drops the line break, so "mill-" / "race" comes out as "mill\\x02race"; it is
written back as a hyphen and a line break.
"""
import pypdfium2 as pdfium

_LINE_END_HYPHEN = "\x02"


def extract_pages(path: str) -> list[str]:
    """Return the text of each page of a PDF, in order ('' for pages without text)."""
    pdf = pdfium.PdfDocument(path)
    try:
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                text = textpage.get_text_bounded()
            finally:
                textpage.close()
                page.close()
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\x00")
            pages.append(text.replace(_LINE_END_HYPHEN, "-\n"))
        return pages
    finally:
        pdf.close()


def extract_text(path: str) -> str:
    """Return the text of all pages, separated by newlines."""
    return "\n".join(p for p in extract_pages(path) if p)
