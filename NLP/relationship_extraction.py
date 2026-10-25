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

import bisect
import csv
import logging
import os

import networkx as nx
from matplotlib.figure import Figure

from common.paths import find_files, unreadable_entries
from common.spreadsheet import safe_row
from common.text_files import SAVED_TEXT_SUFFIX, SavedTextCheck, read_text
from common.text_files import document_text as extract_text_from_file
from NLP.ner_onnx import load_model
from NLP.text_utils import sentence_spans, word_spans

log = logging.getLogger(__name__)

DEFAULT_RELATIONSHIP = "is connected to"
MAX_CONNECTING_WORDS = 8
MIN_SENTENCE_WORDS = 5
# A "sentence" naming more entities than this is a list, an index or a table
# that sentence splitting left whole: its pairs (n * (n - 1) / 2 rows, each
# holding the whole passage) would run to tens of thousands and say nothing.
MAX_SENTENCE_ENTITIES = 40
CSV_COLUMNS = ['Source', 'Source_Type', 'Relationship', 'Target', 'Target_Type', 'Sentence', 'File']


def _sentence_words(sentence: str) -> int:
    """Words in *sentence*: separated by spaces, or for Chinese/Japanese, one per character."""
    return max(len(sentence.split()), len(word_spans(sentence)))


def _connecting(text, free, starts, first, second) -> str:
    """The words between two entities that are not part of another entity.

    *free* holds the (start, end) of the sentence's words outside every entity,
    in order, and *starts* their starts.
    """
    tokens = []
    for start, end in free[bisect.bisect_left(starts, first["end"]):]:
        if end > second["start"] or len(tokens) > MAX_CONNECTING_WORDS:
            break
        tokens.append(text[start:end])
    if not tokens:
        return DEFAULT_RELATIONSHIP
    if len(tokens) > MAX_CONNECTING_WORDS:
        return " ".join(tokens[:MAX_CONNECTING_WORDS]) + " …"
    return " ".join(tokens)


def extract_entities_and_relationships(text, entity_types, cancel=None, crowded=None):
    """
    Relationship rows [source, source_type, relationship, target, target_type,
    sentence] for every pair of entities (of the selected types) that share a
    sentence, in reading order.

    Sentences with more than MAX_SENTENCE_ENTITIES entities are left out; pass
    a list as *crowded* to have their text appended.  A set *cancel* event
    stops the work and returns None.
    """
    entities = sorted((e for e in load_model().predict(text) if e["entity_group"] in entity_types),
                      key=lambda e: e["start"])
    entity_starts = [e["start"] for e in entities]
    relationships = []
    for s_start, s_end in sentence_spans(text):
        if cancel is not None and cancel.is_set():
            return None
        sentence = text[s_start:s_end]
        lo = bisect.bisect_left(entity_starts, s_start)
        hi = bisect.bisect_left(entity_starts, s_end)
        in_sentence = [e for e in entities[lo:hi] if e["end"] <= s_end]
        if len(in_sentence) < 2 or _sentence_words(sentence) < MIN_SENTENCE_WORDS:
            continue
        if len(in_sentence) > MAX_SENTENCE_ENTITIES:
            if crowded is not None:
                crowded.append(sentence)
            continue
        free = [(s_start + s, s_start + e) for _w, s, e in word_spans(sentence)
                if not any(o["start"] <= s_start + s and s_start + e <= o["end"] for o in in_sentence)]
        starts = [s for s, _e in free]
        for i, first in enumerate(in_sentence):
            for second in in_sentence[i + 1:]:
                relationships.append([
                    text[first["start"]:first["end"]], first["entity_group"],
                    _connecting(text, free, starts, first, second),
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
    """Generate and save network graphs of the extracted relationships; returns the files saved.

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
    saved = []
    fig = Figure(figsize=(12, 10), layout="tight")
    ax = fig.subplots()
    node_colors = [ENTITY_COLORS.get(G.nodes[node]['entity_type'], 'gray') for node in G.nodes()]
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, ax=ax, with_labels=True, node_color=node_colors, node_size=1500, font_size=8, alpha=0.8)
    ax.set_title("Entity Relationship Network")
    saved.append(os.path.join(output_dir, "relationship_network.png"))
    fig.savefig(saved[-1], dpi=300, bbox_inches='tight')

    # Create subgraphs for each entity type
    entity_types = {G.nodes[node]['entity_type'] for node in G.nodes()}
    for entity_type in sorted(entity_types):
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
            saved.append(os.path.join(output_dir, f"{entity_type.lower()}_network.png"))
            fig.savefig(saved[-1], dpi=300, bbox_inches='tight')
    return saved


def _save_text(path, text, warnings, rel):
    """Save a PDF's text as *path*, unless a file of that name with other text (the user's own) is there."""
    if os.path.exists(path):
        check = SavedTextCheck()
        check.remember(path[:-len(SAVED_TEXT_SUFFIX)] + ".pdf", text)
        try:
            ours = check.is_saved_text(path, read_text(path))
        except OSError:
            ours = False
        if not ours:
            warnings.append({"input": rel, "message": f"its text was not saved: {os.path.basename(path)}"
                             " already exists with other text"})
            return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def process_files_for_relationships(input_dir, output_dir, extract_text, generate_graph, entity_types,
                                    on_progress=None, cancel=None):
    """Process files and extract relationships.

    on_progress(done, total, current_file) is called before each file; a set
    *cancel* event stops the run (the file being read is left out).  With
    *extract_text*, the text of each PDF is saved as "<name>_text.txt" in the
    matching folder under *output_dir* (beside the PDF when output_dir is
    input_dir), unless a file of that name with other text is there; text
    saved by an earlier run is recognized and not processed again.  Files are
    named by their path relative to *input_dir* in the CSV, 'processed_files',
    'skipped' ({"input": path, "message": why}: files not processed) and
    'warnings' (the same: files processed only in part).
    """
    results = {
        'status': 'success',
        'message': '',
        'relationship_count': 0,
        'file_count': 0,
        'processed_files': [],
        'skipped': [],
        'warnings': [],
        'images': [],
    }

    try:
        unreadable = []
        files = find_files(input_dir, [".txt", ".pdf"], unreadable=unreadable)
        results['skipped'] += unreadable_entries(unreadable, input_dir)

        if not files:
            results['status'] = 'warning'
            results['message'] = 'No text or PDF files found in the input directory.'
            return results

        os.makedirs(output_dir, exist_ok=True)
        all_relationships = []
        saved_texts = SavedTextCheck()

        for i, file_path in enumerate(files):
            if cancel is not None and cancel.is_set():
                break
            rel = os.path.relpath(file_path, input_dir)
            if on_progress:
                on_progress(i, len(files), os.path.basename(file_path))
            try:
                text = extract_text_from_file(file_path)
                saved_texts.remember(file_path, text)
                if saved_texts.is_saved_text(file_path, text):
                    continue   # the text an earlier run saved from the PDF next to it
                if not text.strip():
                    results['skipped'].append({"input": rel, "message": "no text (scanned PDF? run OCR first)"})
                    continue

                crowded = []
                file_relationships = extract_entities_and_relationships(text, entity_types, cancel, crowded)
                if file_relationships is None:
                    break   # cancelled
                for relation in file_relationships:
                    relation.append(rel)
                all_relationships.extend(file_relationships)
                if crowded:
                    results['warnings'].append({"input": rel, "message": (
                        f"{len(crowded)} passage(s) naming more than {MAX_SENTENCE_ENTITIES} entities (lists or"
                        " indexes, read as one sentence) were left out")})

                # Save extracted text if requested
                if extract_text and file_path.lower().endswith('.pdf'):
                    text_output_path = os.path.join(output_dir, os.path.splitext(rel)[0] + SAVED_TEXT_SUFFIX)
                    _save_text(text_output_path, text, results['warnings'], rel)

                results['processed_files'].append(rel)
                results['file_count'] += 1

            except Exception as e:
                log.warning("relationships: cannot process %s: %s", file_path, e)
                results['skipped'].append({"input": rel, "message": f"could not be processed ({e})"})

        # utf-8-sig + newline='' so Excel shows non-Latin names and no blank rows.  Written even
        # without relationships, so the folder never holds an earlier run's results instead.
        csv_path = os.path.join(output_dir, "relationships.csv")
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            writer.writerows(safe_row(row) for row in all_relationships)

        if all_relationships:
            if generate_graph:
                results['images'] = generate_network_graph(
                    [dict(zip(CSV_COLUMNS, row)) for row in all_relationships], output_dir)

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
        extract_text=True,
        generate_graph=True,
        entity_types=["PER", "ORG", "LOC"]
    )
    print(results)
