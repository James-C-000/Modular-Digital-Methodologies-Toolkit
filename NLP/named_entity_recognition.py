#!/usr/bin/env python3
"""Named entity recognition over a folder of PDF/TXT files (see NLP.ner_onnx)."""
import html
import logging
import os
from collections import Counter

from common.paths import find_files, output_stems, unreadable_entries
from common.text_files import SavedTextCheck, document_text
from NLP.ner_onnx import load_model

log = logging.getLogger(__name__)


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
    *cancel* event stops before the next one.  Returns {"files": files analysed,
    "total": files found, "summary": path of the summary HTML,
    "skipped": [{"input": path relative to *directory*, "message": why}]}.

    Each highlighted copy is written next to its document; the summary goes
    in *directory*.
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"{directory} is not a valid directory.")

    summary_html_content = (
        "<html><head><meta charset='utf-8'><title>NER Summary Statistics</title></head><body>\n"
        "<h1>Named Entity Recognition Summary Statistics</h1>\n"
    )

    overall_summary = {}

    unreadable = []
    paths = find_files(directory, [".pdf", ".txt"], unreadable=unreadable)
    stems = output_stems(paths)
    read, skipped = 0, []
    saved_texts = SavedTextCheck()
    for i, file_path in enumerate(paths):
        if cancel is not None and cancel.is_set():
            break
        root, file = os.path.split(file_path)
        rel = os.path.relpath(file_path, directory)
        if on_progress:
            on_progress(i, len(paths), file)
        log.info("ner: %s", file_path)
        try:
            text = document_text(file_path)
        except Exception as e:
            log.warning("ner: cannot read %s: %s", file_path, e)
            skipped.append({"input": rel, "message": f"could not be read ({e})"})
            continue
        saved_texts.remember(file_path, text)
        if saved_texts.is_saved_text(file_path, text):
            skipped.append({"input": rel, "message": "the text Relationships saved from the PDF next to it,"
                                                     " which was analysed itself"})
        elif not text.strip():
            skipped.append({"input": rel, "message": "no text (scanned PDF? run OCR first)"})
        else:
            read += 1
            # Run NER on the entire text by chunking.
            entities = run_ner_on_text(text)
            summary = summarize_entities(entities)

            # Update overall summary
            for label, counter in summary.items():
                if label not in overall_summary:
                    overall_summary[label] = Counter()
                overall_summary[label] += counter

            # Append file summary to overall summary HTML.
            summary_html_content += generate_summary_html(rel, summary)

            # Generate highlighted HTML for the individual document.
            highlight_html = generate_highlight_html(file, text, entities)
            highlight_file = os.path.join(root, f"{stems[file_path]}_Named_Entity_Recognition_Highlight.html")
            with open(highlight_file, "w", encoding="utf-8") as f:
                f.write(highlight_html)

    # Append overall summary statistics.
    if overall_summary:
        summary_html_content += "<h2>Overall Summary</h2>\n"
        summary_html_content += generate_summary_html("All Files", overall_summary)

    summary_html_content += "</body></html>"

    # Save the overall summary HTML file.
    output_summary_file = os.path.join(directory, "Named_Entity_Recognition_Summary.html")
    with open(output_summary_file, "w", encoding="utf-8") as f:
        f.write(summary_html_content)

    log.info("ner: %d of %d file(s) analysed, summary %s", read, len(paths), output_summary_file)
    if on_progress:
        on_progress(read + len(skipped), len(paths), "")
    skipped = unreadable_entries(unreadable, directory) + skipped
    return {"files": read, "total": len(paths), "summary": output_summary_file, "skipped": skipped}


if __name__ == "__main__":
    # Set your input directory path here.
    directory = os.path.join(os.path.dirname(__file__), "input")  # <-- Update this path accordingly.
    main(directory)
