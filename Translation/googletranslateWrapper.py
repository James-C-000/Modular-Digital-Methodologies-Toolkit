#!/usr/bin/env python3
import os
import re
import asyncio
from googletrans import Translator
from pypdf import PdfReader  # pypdf replaces PyPDF2

# ----- Configuration variables (update these by hand) -----
TARGET_LANG = "es"  # Desired target language code (e.g., "en", "es", "fr", "de")
SUFFIX = "_translated"  # Suffix to append to output filenames
DIRECTORY = "/home/james/Work/Aboriginal Sport Circle/Policy Documents/National"  # Path to the directory containing files to translate
MAX_CHARS = 5000  # Maximum characters per translation chunk (adjust if needed)


# --------------------------------------------------------------

def chunk_text(text, max_chars=MAX_CHARS):
    """
    Split the text into chunks of less than max_chars by splitting on sentence boundaries.
    """
    # Split text into sentences (splitting on punctuation followed by whitespace)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(sentence) > max_chars:
                for i in range(0, len(sentence), max_chars):
                    chunks.append(sentence[i:i + max_chars])
            else:
                current_chunk = sentence
        else:
            current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


async def translate_text_with_chunking(text, translator, dest_lang, max_chars=MAX_CHARS):
    """
    Translate the given text by splitting it into chunks (each < max_chars),
    translating each chunk asynchronously, and joining the results.
    """
    chunks = chunk_text(text, max_chars)
    translated_chunks = []
    for idx, chunk in enumerate(chunks, start=1):
        try:
            translated_obj = await translator.translate(chunk, src="auto", dest=dest_lang)
            translated_chunk = translated_obj.text
            print(f"Chunk {idx}/{len(chunks)} translated.")
            translated_chunks.append(translated_chunk)
        except Exception as e:
            print(f"Error translating chunk {idx}: {e}")
            translated_chunks.append(chunk)  # fallback: use original chunk
    return " ".join(translated_chunks)


async def process_txt_file(file_path, translator, dest_lang, suffix):
    """
    Read a .txt file, autodetect its language, translate its content in chunks,
    and write the translated text to a new file with the given suffix.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        if not text.strip():
            print(f"No text found in {file_path}")
            return

        detected = await translator.detect(text)
        print(f"Processing TXT file '{file_path}' (detected language: {detected.lang})")

        translated = await translate_text_with_chunking(text, translator, dest_lang)
        base, _ = os.path.splitext(file_path)
        output_path = f"{base}{suffix}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated)
        print(f"Translated TXT file saved to: {output_path}")
    except Exception as e:
        print(f"Error processing TXT file {file_path}: {e}")


async def process_pdf_file(file_path, translator, dest_lang, suffix):
    """
    Extract text from a PDF file using pypdf, autodetect its language, translate it in chunks,
    and write the translated text as a .txt file with the given suffix.
    """
    try:
        text = ""
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if not text.strip():
            print(f"No text found in {file_path}")
            return

        detected = await translator.detect(text)
        print(f"Processing PDF file '{file_path}' (detected language: {detected.lang})")

        translated = await translate_text_with_chunking(text, translator, dest_lang)
        base, _ = os.path.splitext(file_path)
        output_path = f"{base}{suffix}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated)
        print(f"Translated PDF file saved to: {output_path}")
    except Exception as e:
        print(f"Error processing PDF file {file_path}: {e}")


async def main():
    translator = Translator()
    tasks = []
    # Walk through all files in the specified directory (including subdirectories)
    for root, _, files in os.walk(DIRECTORY):
        for file in files:
            file_path = os.path.join(root, file)
            if file.lower().endswith(".txt"):
                tasks.append(process_txt_file(file_path, translator, TARGET_LANG, SUFFIX))
            elif file.lower().endswith(".pdf"):
                tasks.append(process_pdf_file(file_path, translator, TARGET_LANG, SUFFIX))
    if tasks:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
