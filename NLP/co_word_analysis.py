#!/usr/bin/env python3
import html
import logging
import os
from collections import Counter
from urllib.parse import quote

import networkx as nx
from matplotlib.figure import Figure

from common.paths import output_stems
from common.text_files import document_text
from NLP.text_utils import stopwords, words

log = logging.getLogger(__name__)


def preprocess_text(text, stop_set=frozenset()):
    """
    Lowercased word tokens (any script) without stopwords or one-letter words.
    Han/kana characters are kept as single-character tokens.
    """
    return [w for w in words(text) if w not in stop_set and (len(w) > 1 or not w.isascii())]


def cooccurrence_analysis(tokens, window_size=5):
    """
    Compute co-occurrence counts using a sliding window.
    Returns a Counter where keys are sorted tuples (word1, word2) and values are frequencies.
    """
    cooccurrence = Counter()
    for i in range(len(tokens)):
        window = tokens[i + 1:i + window_size]
        for word in window:
            if tokens[i] != word:
                pair = tuple(sorted((tokens[i], word)))
                cooccurrence[pair] += 1
    return cooccurrence


def visualize_network(cooccurrence, output_path, top_n=30):
    """
    Visualize the co-occurrence network: take the top_n pairs and build a graph.
    Saves the graph as a PNG image.
    """
    top_pairs = cooccurrence.most_common(top_n)
    G = nx.Graph()
    for (w1, w2), freq in top_pairs:
        G.add_edge(w1, w2, weight=freq)

    fig = Figure(figsize=(10, 8))
    ax = fig.subplots()
    pos = nx.spring_layout(G, k=0.5, seed=42)
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    nx.draw(G, pos, ax=ax, with_labels=True, node_color="skyblue", edge_color="gray", width=weights, font_size=10)
    ax.set_title("Co-word Network")
    fig.savefig(output_path)


def escape(text):
    return html.escape(text, quote=True)


def href(path):
    """*path* (relative, OS separators) as a URL for a link or image in a report."""
    return escape(quote(path.replace(os.sep, "/")))


def generate_statistics_html(word_counts, cooccurrence, top_words=20, top_pairs=20):
    """
    Generate an HTML snippet with tables for top frequent words and top co-occurring word pairs.
    """
    html = "<h3>Top Frequent Words</h3><table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Word</th><th>Frequency</th></tr>"
    for word, freq in word_counts.most_common(top_words):
        html += f"<tr><td>{escape(word)}</td><td>{freq}</td></tr>"
    html += "</table>"

    html += "<h3>Top Co-occurring Word Pairs</h3><table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Word Pair</th><th>Frequency</th></tr>"
    for pair, freq in cooccurrence.most_common(top_pairs):
        html += f"<tr><td>{escape(str(pair))}</td><td>{freq}</td></tr>"
    html += "</table>"
    return html


def generate_document_html(file_name, stats_html, network_img_file, output_path):
    """
    Generate an HTML file for a single document including statistics and the network graph image.
    """
    page = f"""<html>
<head><meta charset="utf-8"><title>Co-word Analysis - {escape(file_name)}</title></head>
<body>
<h1>Co-word Analysis for {escape(file_name)}</h1>
{stats_html}
<h2>Co-word Network Graph</h2>
<img src="{href(os.path.basename(network_img_file))}" alt="Co-word Network Graph">
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)


def main(directory, stopword_language="en", extra_stopwords=(), on_progress=None, cancel=None):
    """Run co-word analysis on every PDF/TXT file under *directory*.

    on_progress(done, total, current_file) is called before each file; a set
    *cancel* event stops before the next one.  Returns {"files": files analysed,
    "total": files found, "summary": summary HTML path, "images": network graphs,
    "skipped": [{"input": path relative to *directory*, "message": why}]}.

    Each document's report and graph are written next to it; the summary,
    in *directory*, links to every report.

    stopword_language: ISO 639-1 code from NLP.text_utils.STOPWORD_LANGUAGES,
    or None for no list.  extra_stopwords: additional words to ignore.
    """
    stop_set = set(stopwords(stopword_language)) if stopword_language else set()
    stop_set |= {w.lower() for w in extra_stopwords}
    overall_summary = """<html>
<head><meta charset="utf-8"><title>Co-word Analysis Summary</title></head>
<body>
<h1>Co-word Analysis Summary</h1>
"""
    # Process each PDF or TXT file in the directory.
    paths = sorted(os.path.join(root, file) for root, _dirs, files in os.walk(directory)
                   for file in files if file.lower().endswith((".pdf", ".txt")))
    stems = output_stems(paths)
    read, images, skipped = 0, [], []
    for i, file_path in enumerate(paths):
        if cancel is not None and cancel.is_set():
            break
        root, file = os.path.split(file_path)
        rel = os.path.relpath(file_path, directory)
        if on_progress:
            on_progress(i, len(paths), file)
        log.info("co-words: %s", file_path)
        try:
            text = document_text(file_path)
        except Exception as e:
            log.warning("co-words: cannot read %s: %s", file_path, e)
            skipped.append({"input": rel, "message": f"could not be read ({e})"})
            continue
        if not text.strip():
            skipped.append({"input": rel, "message": "no text (scanned PDF? run OCR first)"})
            continue
        read += 1
        tokens = preprocess_text(text, stop_set)
        word_counts = Counter(tokens)
        cooccur = cooccurrence_analysis(tokens)

        # Visualize co-word network.
        base_name = stems[file_path]
        network_img_file = os.path.join(root, f"{base_name}_co_word_network.png")
        visualize_network(cooccur, network_img_file)
        images.append(network_img_file)

        # Generate statistics HTML snippet.
        stats_html = generate_statistics_html(word_counts, cooccur)

        # Generate individual HTML report for the document.
        html_file = os.path.join(root, f"{base_name}_co_word_analysis.html")
        generate_document_html(file, stats_html, network_img_file, html_file)

        # Append a summary entry to the overall summary.
        overall_summary += f"<h2>{escape(rel)}</h2>\n"
        overall_summary += stats_html
        overall_summary += f"<p><a href='{href(os.path.relpath(html_file, directory))}'>Detailed Analysis</a></p>\n"
    overall_summary += "</body></html>"

    # Save the overall summary document.
    summary_file = os.path.join(directory, "Co_Word_Analysis_Summary.html")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(overall_summary)
    log.info("co-words: %d of %d file(s) analysed, summary %s", read, len(paths), summary_file)
    if on_progress:
        on_progress(read + len(skipped), len(paths), "")
    return {"files": read, "total": len(paths), "summary": summary_file, "images": images, "skipped": skipped}


if __name__ == "__main__":
    # Set your input directory path here.
    directory = os.path.join(os.path.dirname(__file__), "input")  # <-- Update this path accordingly.
    main(directory)
