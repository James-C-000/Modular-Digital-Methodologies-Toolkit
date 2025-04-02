#!/usr/bin/env python3
import os
import re
import webbrowser
from collections import Counter
import nltk
import matplotlib.pyplot as plt
import networkx as nx
from pypdf import PdfReader
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Ensure required NLTK data is downloaded.
nltk.data.path.append("nltk_data")
nltk.download("punkt", download_dir="nltk_data")
nltk.download("punkt_tab", download_dir="nltk_data")
nltk.download("stopwords", download_dir="nltk_data")

def process_pdf(file_path):
    """Extract text from a PDF file using pypdf."""
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return text


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


def preprocess_text(text):
    """
    Preprocess text: lowercase, remove punctuation, tokenize, and remove stopwords.
    """
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = word_tokenize(text)
    stops = set(stopwords.words("english"))
    tokens = [word for word in tokens if word not in stops and len(word) > 1]
    return tokens


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

    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G, k=0.5, seed=42)
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    nx.draw(G, pos, with_labels=True, node_color="skyblue", edge_color="gray", width=weights, font_size=10)
    plt.title("Co-word Network")
    plt.savefig(output_path)
    plt.close()


def generate_statistics_html(word_counts, cooccurrence, top_words=20, top_pairs=20):
    """
    Generate an HTML snippet with tables for top frequent words and top co-occurring word pairs.
    """
    html = "<h3>Top Frequent Words</h3><table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Word</th><th>Frequency</th></tr>"
    for word, freq in word_counts.most_common(top_words):
        html += f"<tr><td>{word}</td><td>{freq}</td></tr>"
    html += "</table>"

    html += "<h3>Top Co-occurring Word Pairs</h3><table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Word Pair</th><th>Frequency</th></tr>"
    for pair, freq in cooccurrence.most_common(top_pairs):
        html += f"<tr><td>{pair}</td><td>{freq}</td></tr>"
    html += "</table>"
    return html


def generate_document_html(file_name, stats_html, network_img_file, output_path):
    """
    Generate an HTML file for a single document including statistics and the network graph image.
    """
    html = f"""<html>
<head><meta charset="utf-8"><title>Co-word Analysis - {file_name}</title></head>
<body>
<h1>Co-word Analysis for {file_name}</h1>
{stats_html}
<h2>Co-word Network Graph</h2>
<img src="{os.path.basename(network_img_file)}" alt="Co-word Network Graph">
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main(directory):
    overall_summary = """<html>
<head><meta charset="utf-8"><title>Co-word Analysis Summary</title></head>
<body>
<h1>Co-word Analysis Summary</h1>
"""
    # Process each PDF or TXT file in the directory.
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith((".pdf", ".txt")):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                text = process_file(file_path)
                if not text.strip():
                    print(f"No text extracted from {file_path}")
                    continue
                tokens = preprocess_text(text)
                word_counts = Counter(tokens)
                cooccur = cooccurrence_analysis(tokens)

                # Visualize co-word network.
                base_name = os.path.splitext(file)[0]
                network_img_file = os.path.join(root, f"{base_name}_co_word_network.png")
                visualize_network(cooccur, network_img_file)

                # Generate statistics HTML snippet.
                stats_html = generate_statistics_html(word_counts, cooccur)

                # Generate individual HTML report for the document.
                html_file = os.path.join(root, f"{base_name}_co_word_analysis.html")
                generate_document_html(file, stats_html, network_img_file, html_file)
                print(f"Saved Co-word Analysis for {file} to {html_file}")

                # Append a summary entry to the overall summary.
                overall_summary += f"<h2>{file}</h2>\n"
                overall_summary += stats_html
                overall_summary += f"<p><a href='{os.path.basename(html_file)}'>Detailed Analysis</a></p>\n"
    overall_summary += "</body></html>"

    # Save the overall summary document.
    summary_file = os.path.join(directory, "Co_Word_Analysis_Summary.html")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(overall_summary)
    print(f"Overall Co-word Analysis Summary saved to {summary_file}")
    webbrowser.open(summary_file)


if __name__ == "__main__":
    # Set your input directory path here.
    directory = "/home/james/PycharmProjects/MDMT/NLP/input"  # <-- Update this path accordingly.
    main(directory)
