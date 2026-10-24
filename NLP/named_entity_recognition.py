#!/usr/bin/env python3
"""Named entity recognition over a folder of PDF/TXT files (see NLP.ner_onnx)."""
import html
import os
from collections import Counter

from common.pdf_text import extract_text
from NLP.ner_onnx import load_model


def process_pdf(file_path):
    """Extract text from a PDF file."""
    try:
        return extract_text(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""


def process_txt(file_path):
    """Read text from a TXT file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        text = ""
    return text


def process_file(file_path):
    """Determine the file type and extract its text."""
    if file_path.lower().endswith(".pdf"):
        return process_pdf(file_path)
    elif file_path.lower().endswith(".txt"):
        return process_txt(file_path)
    else:
        return ""


def run_ner_on_text(text):
    """Entities in *text* (dicts with entity_group, word, start, end, score).

    Long texts are handled by the model's overlapping token windows.
    """
    return load_model().predict(text)


def summarize_entities(entities):
    """
    Aggregate entity statistics.
    Returns a dictionary mapping each entity type to a Counter of recognized entity texts.
    """
    summary = {}
    for ent in entities:
        label = ent["entity_group"]
        word = ent.get("word", "")
        if label not in summary:
            summary[label] = Counter()
        summary[label][word] += 1
    return summary


def generate_summary_html(file_name, summary):
    """
    Generate an HTML snippet containing a summary table for the file.
    The table shows each entity type, its total count, and the top entities.
    """
    snippet = f"<h2>{html.escape(file_name)}</h2>\n"
    snippet += "<table border='1' cellspacing='0' cellpadding='5'>"
    snippet += "<tr><th>Entity Type</th><th>Total Count</th><th>Top Entities (count)</th></tr>"
    for label, counter in summary.items():
        total = sum(counter.values())
        top_entities = counter.most_common(3)  # Display top 3 entities for brevity
        top_str = ", ".join([f"{html.escape(entity)} ({count})" for entity, count in top_entities])
        snippet += f"<tr><td>{label}</td><td>{total}</td><td>{top_str}</td></tr>"
    snippet += "</table><br><hr><br>\n"
    return snippet


def generate_highlight_html(file_name, text, entities):
    """
    Generate an HTML file that highlights named entities in the text.
    The recognized entities are wrapped in <span> tags with a background color.
    """
    # Sort entities by their start index.
    entities = sorted(entities, key=lambda e: e["start"])

    out = f"<html><head><meta charset='utf-8'><title>{html.escape(file_name)} - Highlighted NER</title></head><body>\n"
    out += f"<h2>{html.escape(file_name)}</h2>\n<p>"
    last_idx = 0
    for ent in entities:
        start = ent["start"]
        end = ent["end"]
        label = ent["entity_group"]
        # Define a simple color mapping for common entity types.
        color_map = {
            "PER": "#faa",  # Person: light red
            "ORG": "#afa",  # Organization: light green
            "LOC": "#aaf",  # Location: light blue
            "MISC": "#ffa",  # Miscellaneous: light yellow
            "DATE": "#fda",  # Date: light orange
        }
        color = color_map.get(label, "#ddd")  # default to light gray if not mapped

        if start < last_idx:
            continue  # overlapping entity (should not happen)
        # Append text before the entity.
        out += html.escape(text[last_idx:start])
        # Append highlighted entity text.
        out += f"<span style='background-color: {color};' title='{label}'>{html.escape(text[start:end])}</span>"
        last_idx = end
    out += html.escape(text[last_idx:])
    out += "</p>\n</body></html>"
    return out


def main(directory, on_progress=None, cancel=None):
    """
    Process PDF and TXT files in the directory, run NER on each,
    generate both a summary HTML file with statistics and individual
    HTML files with highlighted entities for each document.

    on_progress(done, total, current_file) is called before each file; a set
    *cancel* event stops before the next one.  Returns {"files": files read,
    "total": files found, "summary": path of the summary HTML}.
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"{directory} is not a valid directory.")

    summary_html_content = (
        "<html><head><meta charset='utf-8'><title>NER Summary Statistics</title></head><body>\n"
        "<h1>Named Entity Recognition Summary Statistics</h1>\n"
    )

    overall_summary = {}

    paths = sorted(os.path.join(root, file) for root, _dirs, files in os.walk(directory)
                   for file in files if file.lower().endswith((".pdf", ".txt")))
    read = 0
    for i, file_path in enumerate(paths):
        if cancel is not None and cancel.is_set():
            break
        file = os.path.basename(file_path)
        if on_progress:
            on_progress(i, len(paths), file)
        read += 1
        print(f"Processing file: {file_path}")
        text = process_file(file_path)
        if text:
            # Run NER on the entire text by chunking.
            entities = run_ner_on_text(text)
            summary = summarize_entities(entities)

            # Update overall summary
            for label, counter in summary.items():
                if label not in overall_summary:
                    overall_summary[label] = Counter()
                overall_summary[label] += counter

            # Append file summary to overall summary HTML.
            summary_html_content += generate_summary_html(file, summary)

            # Generate highlighted HTML for the individual document.
            highlight_html = generate_highlight_html(file, text, entities)
            # Build output file name: replace extension with _highlight.html
            base_name = os.path.splitext(file)[0]
            highlight_file = os.path.join(directory, f"{base_name}_Named_Entity_Recognition_Highlight.html")
            with open(highlight_file, "w", encoding="utf-8") as f:
                f.write(highlight_html)
            print(f"Saved highlighted HTML to {highlight_file}")
        else:
            print(f"No text extracted from {file_path}\n")

    # Append overall summary statistics.
    if overall_summary:
        summary_html_content += "<h2>Overall Summary</h2>\n"
        summary_html_content += generate_summary_html("All Files", overall_summary)

    summary_html_content += "</body></html>"

    # Save the overall summary HTML file.
    output_summary_file = os.path.join(directory, "Named_Entity_Recognition_Summary.html")
    with open(output_summary_file, "w", encoding="utf-8") as f:
        f.write(summary_html_content)

    print(f"NER summary statistics saved to {output_summary_file}")
    if on_progress:
        on_progress(read, len(paths), "")
    return {"files": read, "total": len(paths), "summary": output_summary_file}


if __name__ == "__main__":
    # Set your input directory path here.
    directory = os.path.join(os.path.dirname(__file__), "input")  # <-- Update this path accordingly.
    main(directory)
