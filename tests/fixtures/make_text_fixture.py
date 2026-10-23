"""Regenerate text_sample.pdf: a two-page PDF with a real (selectable) text layer.

Dev-only helper; the PDF is committed.  Uses fpdf2 (an ocrmypdf dependency)
and matplotlib's bundled DejaVu Sans so Cyrillic text is embedded with a
ToUnicode map and extracts correctly.

    python tests/fixtures/make_text_fixture.py
"""
import os

import matplotlib
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = [
    "The archive in москва holds letters from kyiv and from Lisbon . "
    "A clerk in москва copied every letter by hand .",
    "Later letters from kyiv mention the con artist Ada Lovelace met in London in 1843 .",
]


def main():
    font = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=font)
    for text in PAGES:
        pdf.add_page()
        pdf.set_font("DejaVu", size=12)
        pdf.multi_cell(0, 8, text)
    out = os.path.join(HERE, "text_sample.pdf")
    pdf.output(out)
    print(f"Wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
