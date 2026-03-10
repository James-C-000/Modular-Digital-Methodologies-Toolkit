#!/usr/bin/env python3
"""
Relationship Extraction Logic Script
Contains functions for extracting entity relationships from text using regex and NLTK.
"""

import os
import re
import csv
import nltk
import pandas as pd
import networkx as nx
from pypdf import PdfReader
from collections import defaultdict

# Set the matplotlib backend to Agg (non-interactive) to avoid thread-related warnings
import matplotlib

matplotlib.use('Agg')

_nltk_ready = False

_NLTK_PACKAGES = [
    ('tokenizers/punkt_tab', 'punkt_tab'),
    ('taggers/averaged_perceptron_tagger_eng', 'averaged_perceptron_tagger_eng'),
    ('chunkers/maxent_ne_chunker_tab', 'maxent_ne_chunker_tab'),
    ('corpora/words', 'words'),
]


def _ensure_nltk_data():
    """Download required NLTK data on first use."""
    global _nltk_ready
    if _nltk_ready:
        return
    from config import get_nltk_data_dir
    nltk_dir = get_nltk_data_dir()
    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)
    for resource, package in _NLTK_PACKAGES:
        try:
            nltk.data.find(resource)
        except LookupError:
            nltk.download(package, download_dir=nltk_dir, quiet=True)
    _nltk_ready = True


def extract_text_from_file(file_path):
    """Extract text from a text or PDF file"""
    try:
        if file_path.lower().endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif file_path.lower().endswith('.pdf'):
            text = ""
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")
    return ""


def find_verbs_between(tokens, start_idx, end_idx):
    """Find verbs between two positions in a tagged token list"""
    verbs = []

    # Ensure indices are valid
    if start_idx >= end_idx or start_idx < 0 or end_idx >= len(tokens):
        return "is connected to"

    # Look for verbs between the entities
    for i in range(start_idx, end_idx):
        token, tag = tokens[i]
        if tag.startswith('VB'):  # All verb forms (VB, VBD, VBG, etc.)
            verbs.append(token)

    if verbs:
        return " ".join(verbs)

    return "is connected to"  # Default relationship


def extract_entities_and_relationships(text, entity_types):
    """
    Extract named entities and their relationships from text
    using NLTK's named entity recognition.
    """
    relationships = []
    sentences = nltk.sent_tokenize(text)

    for sentence in sentences:
        # Skip very short sentences
        if len(sentence.split()) < 5:
            continue

        # Tokenize and tag the sentence
        tokens = nltk.word_tokenize(sentence)
        tagged_tokens = nltk.pos_tag(tokens)

        # Extract named entities
        tree = nltk.ne_chunk(tagged_tokens)

        # Extract entities from the parse tree
        entities = []
        for subtree in tree:
            if isinstance(subtree, nltk.Tree) and subtree.label() in entity_types:
                entity_text = ' '.join([token for token, pos in subtree.leaves()])
                entity_type = subtree.label()
                # Find start and end positions in the tagged tokens
                start_pos = -1
                end_pos = -1
                for i, (token, _) in enumerate(tagged_tokens):
                    if start_pos == -1 and token == subtree.leaves()[0][0]:
                        start_pos = i
                    if start_pos != -1 and token == subtree.leaves()[-1][0]:
                        end_pos = i + 1
                        break

                entities.append((entity_text, entity_type, start_pos, end_pos))

        # Look for relationships between entity pairs
        for i, (entity1_text, entity1_type, e1_start, e1_end) in enumerate(entities):
            for (entity2_text, entity2_type, e2_start, e2_end) in entities[i + 1:]:
                # Determine if entity1 comes before entity2
                if e1_start < e2_start:
                    # Find relationship (verbs) between the entities
                    relationship = find_verbs_between(tagged_tokens, e1_end, e2_start)
                    relationships.append([
                        entity1_text, entity1_type,
                        relationship,
                        entity2_text, entity2_type,
                        sentence
                    ])
                else:
                    # Reverse the order
                    relationship = find_verbs_between(tagged_tokens, e2_end, e1_start)
                    relationships.append([
                        entity2_text, entity2_type,
                        relationship,
                        entity1_text, entity1_type,
                        sentence
                    ])

    return relationships


def extract_relationships_from_file(file_path, entity_types):
    """Extract relationships from a single file"""
    text = extract_text_from_file(file_path)
    if not text:
        return []

    # Extract entities and relationships
    relationships = extract_entities_and_relationships(text, entity_types)

    # Add filename to each relationship
    filename = os.path.basename(file_path)
    for relation in relationships:
        relation.append(filename)

    return relationships


def generate_network_graph(df, output_dir):
    """Generate and save network graphs of the extracted relationships"""
    # Use the Agg backend which is thread-safe and doesn't require a GUI
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # Create entity graph
    G = nx.Graph()

    # Define entity colors
    entity_colors = {
        'PERSON': 'skyblue',
        'ORGANIZATION': 'lightgreen',
        'GPE': 'salmon',
        'LOCATION': 'orange',
        'FACILITY': 'purple',
        'DATE': 'yellow',
        'TIME': 'brown',
        'MONEY': 'green',
        'PERCENT': 'pink',
        'PRODUCT': 'gray'
    }

    # Add nodes and edges
    for _, row in df.iterrows():
        source = row['Source']
        target = row['Target']
        source_type = row['Source_Type']
        target_type = row['Target_Type']

        # Add nodes with entity type attribute
        if not G.has_node(source):
            G.add_node(source, entity_type=source_type)
        if not G.has_node(target):
            G.add_node(target, entity_type=target_type)

        # Add edge
        if not G.has_edge(source, target):
            G.add_edge(source, target, relationship=row['Relationship'])

    # Save the full graph
    plt.figure(figsize=(12, 10))

    # Get node colors based on entity type
    node_colors = [entity_colors.get(G.nodes[node]['entity_type'], 'gray') for node in G.nodes()]

    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=1500, font_size=8, alpha=0.8)

    # Save full network graph
    plt.title("Entity Relationship Network")

    # Use Figure.tight_layout() instead of plt.tight_layout() to avoid warnings
    fig = plt.gcf()
    fig.set_tight_layout(True)

    plt.savefig(os.path.join(output_dir, "relationship_network.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # Create subgraphs for each entity type
    entity_types = set()
    for node in G.nodes():
        entity_types.add(G.nodes[node]['entity_type'])

    for entity_type in entity_types:
        subgraph_nodes = [node for node in G.nodes() if G.nodes[node]['entity_type'] == entity_type]
        if len(subgraph_nodes) > 1:  # Only create graphs with at least 2 nodes
            subgraph = G.subgraph(subgraph_nodes)

            plt.figure(figsize=(10, 8))
            pos = nx.spring_layout(subgraph, seed=42)
            nx.draw(subgraph, pos, with_labels=True,
                    node_color=entity_colors.get(entity_type, 'gray'),
                    node_size=1500, font_size=8, alpha=0.8)

            plt.title(f"{entity_type} Relationship Network")

            # Use Figure.tight_layout() instead of plt.tight_layout()
            fig = plt.gcf()
            fig.set_tight_layout(True)

            plt.savefig(os.path.join(output_dir, f"{entity_type.lower()}_network.png"), dpi=300, bbox_inches='tight')
            plt.close()


def process_files_for_relationships(input_dir, output_dir, model_name, extract_text, generate_graph, entity_types):
    """Process files and extract relationships"""
    _ensure_nltk_data()

    # Set non-interactive backend for matplotlib at the beginning
    import matplotlib
    matplotlib.use('Agg')

    results = {
        'status': 'success',
        'message': '',
        'relationship_count': 0,
        'file_count': 0,
        'processed_files': []
    }

    # Since we're not using spaCy, model_name is ignored

    try:
        # Get all files in input directory
        files = []
        for root, _, filenames in os.walk(input_dir):
            for filename in filenames:
                if filename.lower().endswith(('.txt', '.pdf')):
                    files.append(os.path.join(root, filename))

        if not files:
            results['status'] = 'warning'
            results['message'] = 'No text or PDF files found in the input directory.'
            return results

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Process each file
        all_relationships = []

        for file_path in files:
            try:
                # Extract text from file
                text = extract_text_from_file(file_path)

                if not text:
                    continue

                # Extract relationships
                file_relationships = extract_relationships_from_file(file_path, entity_types)
                all_relationships.extend(file_relationships)

                # Save extracted text if requested
                if extract_text:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    text_output_path = os.path.join(output_dir, f"{base_name}_text.txt")
                    with open(text_output_path, 'w', encoding='utf-8') as f:
                        f.write(text)

                results['processed_files'].append(os.path.basename(file_path))
                results['file_count'] += 1

            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")

        # Create output files
        if all_relationships:
            # Convert to DataFrame
            df = pd.DataFrame(all_relationships,
                              columns=['Source', 'Source_Type', 'Relationship',
                                       'Target', 'Target_Type', 'Sentence', 'File'])

            # Save to CSV
            csv_path = os.path.join(output_dir, "relationships.csv")
            df.to_csv(csv_path, index=False)

            # Generate network graph if requested
            if generate_graph:
                generate_network_graph(df, output_dir)

            results['relationship_count'] = len(df)
            results['message'] = f"Extraction complete. Found {len(df)} relationships."
        else:
            results['status'] = 'warning'
            results['message'] = "No relationships found in the specified files."

    except Exception as e:
        results['status'] = 'error'
        results['message'] = f"An error occurred: {str(e)}"

    return results


# For testing
if __name__ == "__main__":
    results = process_files_for_relationships(
        input_dir="./test_docs",
        output_dir="./test_output",
        model_name=None,  # Not used with NLTK implementation
        extract_text=True,
        generate_graph=True,
        entity_types=["PERSON", "ORGANIZATION", "GPE"]
    )
    print(results)