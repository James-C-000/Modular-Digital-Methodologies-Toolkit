"""PDF text extraction shared by every module (pypdfium2, already required by ocrmypdf).

Returns text per page so callers can report page numbers.  Scanned PDFs
without a text layer yield empty strings; run them through OCR first.
"""
import pypdfium2 as pdfium


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
            pages.append(text.replace("\r\n", "\n").replace("\r", "\n").strip("\x00"))
        return pages
    finally:
        pdf.close()


def extract_text(path: str) -> str:
    """Return the text of all pages, separated by newlines."""
    return "\n".join(p for p in extract_pages(path) if p)
