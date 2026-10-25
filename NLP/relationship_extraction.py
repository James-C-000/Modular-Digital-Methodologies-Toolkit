#!/usr/bin/env python3
"""
Relationship extraction: pairs of named entities that occur in the same sentence.

Entities come from the NER model (NLP.ner_onnx), so entity types are the
model's labels (PER, ORG, LOC, DATE) rather than NLTK's PERSON/ORGANIZATION/GPE.
The "Relationship" column holds the connecting words between the two entities
in the sentence (up to eight, excluding other entities' text), or
"is connected to" when there are none.  (v2.0.x used NLTK's part-of-speech
tagger to keep only the verbs; MDMT no longer ships a POS tagger.)
"""

import csv
import logging
import os

import networkx as nx
from matplotlib.figure import Figure

from common.text_files import document_text as extract_text_from_file
from NLP.ner_onnx import load_model
from NLP.text_utils import sentence_spans, word_spans

log = logging.getLogger(__name__)

DEFAULT_RELATIONSHIP = "is connected to"
MAX_CONNECTING_WORDS = 8
MIN_SENTENCE_WORDS = 5
CSV_COLUMNS = ['Source', 'Source_Type', 'Relationship', 'Target', 'Target_Type', 'Sentence', 'File']


def connecting_words(text, start, end, other_entities):
    """Words in text[start:end] that are not part of another entity."""
    tokens = [w for w, s, e in word_spans(text[start:end])
              if not any(o["start"] <= start + s and start + e <= o["end"] for o in other_entities)]
    if not tokens:
        return DEFAULT_RELATIONSHIP
    if len(tokens) > MAX_CONNECTING_WORDS:
        return " ".join(tokens[:MAX_CONNECTING_WORDS]) + " …"
    return " ".join(tokens)


def extract_entities_and_relationships(text, entity_types):
    """
    Relationship rows [source, source_type, relationship, target, target_type,
    sentence] for every pair of entities (of the selected types) that share a
    sentence, in reading order.
    """
    entities = [e for e in load_model().predict(text) if e["entity_group"] in entity_types]
    relationships = []
    for s_start, s_end in sentence_spans(text):
        sentence = text[s_start:s_end]
        if len(sentence.split()) < MIN_SENTENCE_WORDS:
            continue
        in_sentence = [e for e in entities if s_start <= e["start"] and e["end"] <= s_end]
        for i, first in enumerate(in_sentence):
            for second in in_sentence[i + 1:]:
                others = [e for e in in_sentence if e is not first and e is not second]
                relationships.append([
                    text[first["start"]:first["end"]], first["entity_group"],
                    connecting_words(text, first["end"], second["start"], others),
                    text[second["start"]:second["end"]], second["entity_group"],
                    sentence,
                ])
    return relationships


ENTITY_COLORS = {
    'PER': 'skyblue',
    'ORG': 'lightgreen',
    'LOC': 'salmon',
    'DATE': 'yellow',
    'MISC': 'plum',
}


def generate_network_graph(rows, output_dir):
    """Generate and save network graphs of the extracted relationships.

    rows: dicts with the CSV_COLUMNS keys.
    """
    G = nx.Graph()
    for row in rows:
        source, target = row['Source'], row['Target']
        if not G.has_node(source):
            G.add_node(source, entity_type=row['Source_Type'])
        if not G.has_node(target):
            G.add_node(target, entity_type=row['Target_Type'])
        if not G.has_edge(source, target):
            G.add_edge(source, target, relationship=row['Relationship'])

    # Save the full graph
    fig = Figure(figsize=(12, 10), layout="tight")
    ax = fig.subplots()
    node_colors = [ENTITY_COLORS.get(G.nodes[node]['entity_type'], 'gray') for node in G.nodes()]
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, ax=ax, with_labels=True, node_color=node_colors, node_size=1500, font_size=8, alpha=0.8)
    ax.set_title("Entity Relationship Network")
    fig.savefig(os.path.join(output_dir, "relationship_network.png"), dpi=300, bbox_inches='tight')

    # Create subgraphs for each entity type
    entity_types = {G.nodes[node]['entity_type'] for node in G.nodes()}
    for entity_type in entity_types:
        subgraph_nodes = [node for node in G.nodes() if G.nodes[node]['entity_type'] == entity_type]
        if len(subgraph_nodes) > 1:  # Only create graphs with at least 2 nodes
            subgraph = G.subgraph(subgraph_nodes)
            fig = Figure(figsize=(10, 8), layout="tight")
            ax = fig.subplots()
            pos = nx.spring_layout(subgraph, seed=42)
            nx.draw(subgraph, pos, ax=ax, with_labels=True,
                    node_color=ENTITY_COLORS.get(entity_type, 'gray'),
                    node_size=1500, font_size=8, alpha=0.8)
            ax.set_title(f"{entity_type} Relationship Network")
            fig.savefig(os.path.join(output_dir, f"{entity_type.lower()}_network.png"), dpi=300, bbox_inches='tight')


def _is_extracted_text(path):
    """A "<name>_text.txt" written by a previous run next to "<name>.pdf"."""
    stem = path[:-len("_text.txt")] if path.lower().endswith("_text.txt") else None
    return stem is not None and os.path.isfile(stem + ".pdf")


def process_files_for_relationships(input_dir, output_dir, model_name, extract_text, generate_graph, entity_types,
                                    on_progress=None, cancel=None):
    """Process files and extract relationships (model_name is unused).

    on_progress(done, total, current_file) is called before each file; a set
    *cancel* event stops before the next one.  With *extract_text*, the text of
    each PDF is saved as "<name>_text.txt" in the matching folder under
    *output_dir* (beside the PDF when output_dir is input_dir); text saved by
    an earlier run is not processed again.  Files are named by their path
    relative to *input_dir* in the CSV, 'processed_files' and 'skipped'
    ({"input": path, "message": why}).
    """
    results = {
        'status': 'success',
        'message': '',
        'relationship_count': 0,
        'file_count': 0,
        'processed_files': [],
        'skipped': [],
        'images': [],
    }

    try:
        files = []
        for root, _, filenames in os.walk(input_dir):
            for filename in filenames:
                path = os.path.join(root, filename)
                if filename.lower().endswith(('.txt', '.pdf')) and not _is_extracted_text(path):
                    files.append(path)

        if not files:
            results['status'] = 'warning'
            results['message'] = 'No text or PDF files found in the input directory.'
            return results

        os.makedirs(output_dir, exist_ok=True)
        all_relationships = []

        files.sort()
        for i, file_path in enumerate(files):
            if cancel is not None and cancel.is_set():
                break
            rel = os.path.relpath(file_path, input_dir)
            if on_progress:
                on_progress(i, len(files), os.path.basename(file_path))
            try:
                text = extract_text_from_file(file_path)
                if not text.strip():
                    results['skipped'].append({"input": rel, "message": "no text (scanned PDF? run OCR first)"})
                    continue

                file_relationships = extract_entities_and_relationships(text, entity_types)
                for relation in file_relationships:
                    relation.append(rel)
                all_relationships.extend(file_relationships)

                # Save extracted text if requested
                if extract_text and file_path.lower().endswith('.pdf'):
                    text_output_path = os.path.join(output_dir, os.path.splitext(rel)[0] + "_text.txt")
                    os.makedirs(os.path.dirname(text_output_path), exist_ok=True)
                    with open(text_output_path, 'w', encoding='utf-8') as f:
                        f.write(text)

                results['processed_files'].append(rel)
                results['file_count'] += 1

            except Exception as e:
                log.warning("relationships: cannot process %s: %s", file_path, e)
                results['skipped'].append({"input": rel, "message": f"could not be processed ({e})"})

        if all_relationships:
            # utf-8-sig + newline='' so Excel shows non-Latin names and no blank rows.
            csv_path = os.path.join(output_dir, "relationships.csv")
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)
                writer.writerows(all_relationships)

            if generate_graph:
                generate_network_graph([dict(zip(CSV_COLUMNS, row)) for row in all_relationships], output_dir)
                results['images'] = sorted(os.path.join(output_dir, f) for f in os.listdir(output_dir)
                                           if f.endswith('_network.png'))

            results['relationship_count'] = len(all_relationships)
            results['message'] = f"Extraction complete. Found {len(all_relationships)} relationships."
        else:
            results['status'] = 'warning'
            results['message'] = "No relationships found in the specified files."

    except Exception as e:
        results['status'] = 'error'
        results['message'] = f"An error occurred: {str(e)}"

    if on_progress and results['status'] != 'error':
        done = results['file_count'] + len(results['skipped'])
        on_progress(done, done, "")
    return results


# For testing
if __name__ == "__main__":
    results = process_files_for_relationships(
        input_dir="./test_docs",
        output_dir="./test_output",
        model_name=None,
        extract_text=True,
        generate_graph=True,
        entity_types=["PER", "ORG", "LOC"]
    )
    print(results)
