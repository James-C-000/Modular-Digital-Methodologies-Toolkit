"""OCR batch processing using ocrmypdf.

Tesseract finds its language data through ``TESSDATA_PREFIX``, which
``OCR.tessdata.configure_tessdata()`` points at MDMT's managed tessdata
directory at startup.
"""

import os
import shutil
import sys

import ocrmypdf
import ocrmypdf.subprocess

from common.proc import hide_console_windows_in

hide_console_windows_in(ocrmypdf.subprocess)

GHOSTSCRIPT_DOWNLOAD_URL = "https://ghostscript.com/releases/gsdnld.html"

TESSERACT_LANGUAGES = {
    "Afrikaans": "afr",
    "Albanian": "sqi",
    "Amharic": "amh",
    "Arabic": "ara",
    "Armenian": "hye",
    "Assamese": "asm",
    "Azerbaijani": "aze",
    "Azerbaijani (Cyrillic)": "aze_cyrl",
    "Basque": "eus",
    "Belarusian": "bel",
    "Bengali": "ben",
    "Bosnian": "bos",
    "Breton": "bre",
    "Bulgarian": "bul",
    "Burmese": "mya",
    "Catalan": "cat",
    "Cebuano": "ceb",
    "Central Khmer": "khm",
    "Cherokee": "chr",
    "Chinese (Simplified)": "chi_sim",
    "Chinese (Traditional)": "chi_tra",
    "Corsican": "cos",
    "Croatian": "hrv",
    "Czech": "ces",
    "Danish": "dan",
    "Dutch": "nld",
    "Dzongkha": "dzo",
    "English": "eng",
    "English (Middle)": "enm",
    "Esperanto": "epo",
    "Estonian": "est",
    "Faroese": "fao",
    "Filipino": "fil",
    "Finnish": "fin",
    "French": "fra",
    "French (Middle)": "frm",
    "Frisian": "fry",
    "Gaelic (Scottish)": "gla",
    "Galician": "glg",
    "Georgian": "kat",
    "German": "deu",
    "German (Fraktur)": "frk",
    "Greek": "ell",
    "Greek (Ancient)": "grc",
    "Gujarati": "guj",
    "Haitian Creole": "hat",
    "Hebrew": "heb",
    "Hindi": "hin",
    "Hungarian": "hun",
    "Icelandic": "isl",
    "Indonesian": "ind",
    "Inuktitut": "iku",
    "Irish": "gle",
    "Italian": "ita",
    "Italian (Old)": "ita_old",
    "Japanese": "jpn",
    "Javanese": "jav",
    "Kannada": "kan",
    "Kazakh": "kaz",
    "Kirghiz": "kir",
    "Korean": "kor",
    "Kurdish (Arabic)": "kur_ara",
    "Lao": "lao",
    "Latin": "lat",
    "Latvian": "lav",
    "Lithuanian": "lit",
    "Luxembourgish": "ltz",
    "Macedonian": "mkd",
    "Malay": "msa",
    "Malayalam": "mal",
    "Maltese": "mlt",
    "Maori": "mri",
    "Marathi": "mar",
    "Math/Equations": "equ",
    "Mongolian": "mon",
    "Nepali": "nep",
    "Norwegian": "nor",
    "Occitan": "oci",
    "Oriya": "ori",
    "Pashto": "pus",
    "Persian": "fas",
    "Polish": "pol",
    "Portuguese": "por",
    "Punjabi": "pan",
    "Quechua": "que",
    "Romanian": "ron",
    "Russian": "rus",
    "Sanskrit": "san",
    "Serbian": "srp",
    "Serbian (Latin)": "srp_latn",
    "Sindhi": "snd",
    "Sinhala": "sin",
    "Slovak": "slk",
    "Slovenian": "slv",
    "Spanish": "spa",
    "Spanish (Old)": "spa_old",
    "Sundanese": "sun",
    "Swahili": "swa",
    "Swedish": "swe",
    "Syriac": "syr",
    "Tagalog": "tgl",
    "Tajik": "tgk",
    "Tamil": "tam",
    "Tatar": "tat",
    "Telugu": "tel",
    "Thai": "tha",
    "Tibetan": "bod",
    "Tigrinya": "tir",
    "Tonga": "ton",
    "Turkish": "tur",
    "Ukrainian": "ukr",
    "Urdu": "urd",
    "Uyghur": "uig",
    "Uzbek": "uzb",
    "Uzbek (Cyrillic)": "uzb_cyrl",
    "Vietnamese": "vie",
    "Welsh": "cym",
    "Yiddish": "yid",
    "Yoruba": "yor",
}


# Data files that are not languages but can be downloaded alongside them.
TESSERACT_EXTRA_DATA = {
    "Orientation & script detection (needed for Rotate Pages)": "osd",
}


def downloadable_tessdata() -> dict[str, str]:
    """All tessdata files offered on the Downloads page: display name -> code."""
    return {**TESSERACT_LANGUAGES, **TESSERACT_EXTRA_DATA}


def find_ghostscript() -> str | None:
    """Return the Ghostscript executable ocrmypdf would use, or None.

    PDF/A output needs Ghostscript, which MDMT does not bundle (it is AGPL).
    On Windows ocrmypdf only supports the 64-bit ``gswin64c`` and also looks
    in the registry and Program Files, so we reuse its search path there.
    """
    if sys.platform == "win32":
        search_path = None
        try:
            from ocrmypdf.subprocess._windows import shim_env_path
            search_path = shim_env_path()
        except Exception:
            pass
        return shutil.which("gswin64c", path=search_path)
    return shutil.which("gs")


def find_pdfs_in_directory(directory: str) -> list[str]:
    """Recursively find all PDF files in a directory."""
    pdfs = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def build_ocr_params(
    language_codes: list[str],
    deskew: bool,
    rotate_pages: bool,
    rotate_threshold: int,
    redo_ocr: bool,
    output_type: str,
    sidecar_path: str | None,
) -> dict:
    """Build a parameter dict for ocrmypdf.ocr."""
    params = {
        "language": "+".join(language_codes),
        "deskew": deskew,
        "rotate_pages": rotate_pages,
        "redo_ocr": redo_ocr,
        "output_type": output_type,
    }
    if rotate_pages:
        params["rotate_pages_threshold"] = rotate_threshold
    if sidecar_path:
        params["sidecar"] = sidecar_path
    return params


def run_ocr_file(
    pdf_path: str,
    out_path: str,
    language_codes: list[str],
    deskew: bool = False,
    rotate_pages: bool = False,
    rotate_threshold: int = 6,
    redo_ocr: bool = False,
    output_type: str = "pdf",
    sidecar_path: str | None = None,
) -> dict:
    """OCR one PDF. Returns a result dict with 'status' and 'input'."""
    params = build_ocr_params(
        language_codes=language_codes,
        deskew=deskew,
        rotate_pages=rotate_pages,
        rotate_threshold=rotate_threshold,
        redo_ocr=redo_ocr,
        output_type=output_type,
        sidecar_path=sidecar_path,
    )
    try:
        ocrmypdf.ocr(pdf_path, out_path, progress_bar=False, **params)
        return {"status": "success", "input": pdf_path}
    except Exception as e:
        return {"status": "error", "input": pdf_path, "message": str(e)}


def run_ocr_batch(
    input_dir: str,
    output_dir: str,
    language_names: list[str],
    deskew: bool = False,
    rotate_pages: bool = False,
    rotate_threshold: int = 6,
    redo_ocr: bool = False,
    output_type: str = "pdf",
    extract_text: bool = False,
    on_progress=None,
    cancel=None,
) -> list[dict]:
    """Run OCR on all PDFs in input_dir, writing results to output_dir.

    on_progress(done, total, current_file) is called before each file; a set
    *cancel* event stops the batch before the next file.
    """
    os.makedirs(output_dir, exist_ok=True)

    language_codes = [TESSERACT_LANGUAGES[name] for name in language_names if name in TESSERACT_LANGUAGES]
    if not language_codes:
        return []

    pdfs = find_pdfs_in_directory(input_dir)
    results = []

    for i, pdf_path in enumerate(pdfs):
        if cancel is not None and cancel.is_set():
            break
        if on_progress:
            on_progress(i, len(pdfs), os.path.basename(pdf_path))
        rel_path = os.path.relpath(pdf_path, input_dir)
        out_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        sidecar_path = None
        if extract_text:
            sidecar_path = os.path.splitext(out_path)[0] + ".txt"

        results.append(run_ocr_file(
            pdf_path,
            out_path,
            language_codes,
            deskew=deskew,
            rotate_pages=rotate_pages,
            rotate_threshold=rotate_threshold,
            redo_ocr=redo_ocr,
            output_type=output_type,
            sidecar_path=sidecar_path,
        ))

    if on_progress:
        on_progress(len(results), len(pdfs), "")
    return results
