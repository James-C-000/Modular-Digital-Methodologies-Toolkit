"""Regenerate ocr_sample.pdf: a one-page, image-only PDF (no text layer).

Dev-only helper; the generated PDF is committed so CI and the self-test
don't depend on fonts being installed. Uses the DejaVu Sans font that ships
with matplotlib so the output is reproducible.

    python tests/fixtures/make_ocr_fixture.py
"""
import os

import matplotlib
from PIL import Image, ImageDraw, ImageFont

TEXT = ["The lighthouse keeper", "recorded the storm", "in his logbook."]
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    font_path = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
    font = ImageFont.truetype(font_path, 48)
    img = Image.new("L", (900, 300), 255)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(TEXT):
        draw.text((40, 30 + i * 80), line, fill=0, font=font)
    img = img.convert("1")
    out = os.path.join(HERE, "ocr_sample.pdf")
    img.save(out, "PDF", resolution=150)
    print(f"Wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
