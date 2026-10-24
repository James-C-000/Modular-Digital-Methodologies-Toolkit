"""Relationship extraction page."""
from nicegui import ui

from common.paths import folder_problem
from NLP.ner_onnx import DEFAULT_NER_MODEL, NER_MODELS
from pages.components import (
    FolderField, JobPanel, hint, page_header, remember, run_button, saved, section, start_job,
)

ENTITY_TYPES = {"PER": "PER — people", "ORG": "ORG — organizations",
                "LOC": "LOC — places", "DATE": "DATE — dates"}
ENTITY_TYPES = {k: v for k, v in ENTITY_TYPES.items() if k in NER_MODELS[DEFAULT_NER_MODEL]["labels"]}
DEFAULT_TYPES = ["PER", "ORG", "LOC"]


def relationships_page():
    page_header("Relationships", "Find which entities appear together, and the words that connect them")

    with section("Folder"):
        src = FolderField("Input folder (.txt and .pdf, searched recursively)", "defaults.relationships_input_dir")
        hint("Writes relationships.csv and the network graphs into the input folder.")

    with section("Entities"):
        types = remember(ui.select(ENTITY_TYPES, multiple=True, label="Entity types",
                                   value=[t for t in saved("defaults.relationships_types", DEFAULT_TYPES)
                                          if t in ENTITY_TYPES]).classes("w-full").props("use-chips"),
                         "defaults.relationships_types")
        hint("Entities come from the multilingual NER model (Downloads page). The Relationship column lists the"
             " words connecting each pair of entities in a sentence.")

    with section("Options"):
        with ui.row():
            extract_text = remember(ui.checkbox("Save text extracted from PDFs",
                                                value=saved("defaults.relationships_extract_text", False)),
                                    "defaults.relationships_extract_text")
            graph = remember(ui.checkbox("Draw network graphs", value=saved("defaults.relationships_graph", True)),
                             "defaults.relationships_graph")
        hint("Saved text goes next to each PDF as <name>_text.txt and is not processed again on later runs.")

    def describe(job):
        result = job.result or {}
        if result.get("status") == "success":
            ui.label(f"{result['relationship_count']} relationship(s) in {result['file_count']} file(s).") \
                .classes("text-body2")
        elif result.get("message"):
            ui.label(result["message"]).classes("text-body2 text-warning")

    def start():
        problem = folder_problem(src.value)
        if problem:
            return src.error(problem)
        if not types.value:
            return ui.notify("Select at least one entity type.", type="warning")
        folder, chosen = src.value, list(types.value)
        extract, draw = extract_text.value, graph.value

        def work(job):
            from NLP.relationship_extraction import process_files_for_relationships
            job.progress(0, 0, "Loading the NER model...")
            result = process_files_for_relationships(folder, folder, None, 1 if extract else 0, 1 if draw else 0,
                                                     chosen, on_progress=job.progress, cancel=job.cancel_event)
            if result["status"] == "error":
                raise RuntimeError(result["message"])
            for image in result.get("images", []):
                job.add_image(image)
            return result

        start_job("relationships", "Relationships", work, output_dir=folder)

    run_button("Extract relationships", start, "relationships")
    JobPanel("relationships", describe=describe)
