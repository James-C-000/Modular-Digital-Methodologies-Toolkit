"""Document loaders for RAG: plain Python, no LangChain.

Each loader returns Sections: text plus the page it came from (PDFs only;
1-based).  Supported: .txt .md .json .csv (stdlib), .pdf (pypdfium2 via
common.pdf_text), .docx (zipfile + ElementTree), .html/.htm (html.parser).
"""
import csv
import io
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser

from common.paths import find_files
from common.text_files import read_text


@dataclass(frozen=True)
class Section:
    text: str
    page: int | None = None   # 1-based page number for PDFs


def _load_plain(path):
    return [Section(read_text(path))]


def _flatten_json(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten_json(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _flatten_json(item, f"{prefix}[{i}]")
    else:
        yield f"{prefix}: {value}" if prefix else str(value)


def _load_json(path):
    try:
        data = json.loads(read_text(path))
    except ValueError:
        return _load_plain(path)  # not valid JSON: index it as text
    return [Section("\n".join(_flatten_json(data)))]


def _load_csv(path):
    text = read_text(path)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [row for row in csv.reader(io.StringIO(text), dialect) if any(v.strip() for v in row)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]

    def name(i):   # a column without a heading (more fields than the header row has)
        return header[i] if i < len(header) and header[i].strip() else f"column {i + 1}"

    lines = [" | ".join(f"{name(i)}: {v}" for i, v in enumerate(row) if v.strip()) for row in body]
    return [Section("\n".join(line for line in lines if line))]


def _load_pdf(path):
    from common.pdf_text import extract_pages
    return [Section(text, page=i + 1) for i, text in enumerate(extract_pages(path)) if text.strip()]


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paragraph_text(para) -> str:
    parts = []
    for node in para.iter():
        if node.tag == _W + "t":
            parts.append(node.text or "")
        elif node.tag == _W + "tab":
            parts.append("\t")
        elif node.tag in (_W + "br", _W + "cr"):
            parts.append("\n")
    return "".join(parts).strip()


# Elements that only wrap others: content controls (cover pages, tables of
# contents, template fields), custom XML, tracked insertions.
_WRAPPERS = {_W + "sdt", _W + "sdtContent", _W + "customXml", _W + "ins", _W + "moveTo", _W + "smartTag"}


def _children(element, tags):
    """Children of *element* with one of *tags*, looking inside wrapper elements."""
    for child in element:
        if child.tag in tags:
            yield child
        elif child.tag in _WRAPPERS:
            yield from _children(child, tags)


def _blocks_in(container):
    """Paragraph texts in order; each table row becomes 'cell | cell'."""
    for block in _children(container, {_W + "p", _W + "tbl"}):
        if block.tag == _W + "p":
            text = _paragraph_text(block)
            if text:
                yield text
            continue
        for row in _children(block, {_W + "tr"}):
            cells = [" ".join(_blocks_in(cell)) for cell in _children(row, {_W + "tc"})]
            if any(cells):
                yield " | ".join(cells)


def _docx_blocks(xml_bytes):
    """Paragraph texts in document order; each table row becomes 'cell | cell'."""
    root = ET.fromstring(xml_bytes)
    containers = [root.find(_W + "body")] if root.find(_W + "body") is not None else [root]
    containers += [el for el in root if el.tag in (_W + "footnote", _W + "endnote")]
    for container in containers:
        yield from _blocks_in(container)


def _load_docx(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        blocks = list(_docx_blocks(z.read("word/document.xml")))
        for extra in ("word/footnotes.xml", "word/endnotes.xml"):
            if extra in names:
                blocks += list(_docx_blocks(z.read(extra)))
    return [Section("\n".join(blocks))]


class _HtmlText(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
              "header", "footer", "blockquote", "pre", "table", "ul", "ol", "dd", "dt", "hr", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP and tag != "head":
            self.skipping += 1
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and tag != "head" and self.skipping:
            self.skipping -= 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip(" |") for line in raw.split("\n"))
        return "\n".join(line for line in lines if line)


def _load_html(path):
    parser = _HtmlText()
    parser.feed(read_text(path))
    parser.close()
    return [Section(parser.text())]


SUPPORTED_EXTENSIONS = {
    ".txt": _load_plain, ".md": _load_plain, ".json": _load_json, ".csv": _load_csv,
    ".pdf": _load_pdf, ".docx": _load_docx, ".html": _load_html, ".htm": _load_html,
}


def find_documents(directory: str, unreadable: list | None = None) -> list[str]:
    """Supported files under *directory*, sorted by relative path (see find_files for *unreadable*)."""
    found = find_files(directory, SUPPORTED_EXTENSIONS, skip_hidden_dirs=True, unreadable=unreadable)
    return sorted(found, key=lambda p: os.path.relpath(p, directory).lower())


def load_document(path: str) -> list[Section]:
    """Sections of one document (ValueError naming the file if it cannot be read)."""
    loader = SUPPORTED_EXTENSIONS.get(os.path.splitext(path)[1].lower())
    if loader is None:
        raise ValueError(f"unsupported file type: {os.path.basename(path)}")
    try:
        sections = loader(path)
    except Exception as e:
        raise ValueError(f"could not read {os.path.basename(path)}: {e}") from e
    return [s for s in sections if s.text.strip()]
