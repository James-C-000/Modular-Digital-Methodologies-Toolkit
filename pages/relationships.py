"""Relationship extraction page."""
import os
from nicegui import ui, run
from pages.pickers import browse_dir
from config import AppConfig

from NLP.ner_onnx import DEFAULT_NER_MODEL, NER_MODELS

ENTITY_TYPES = {"PER": "PER \u2014 people", "ORG": "ORG \u2014 organizations",
                "LOC": "LOC \u2014 places", "DATE": "DATE \u2014 dates"}
ENTITY_TYPES = {k: v for k, v in ENTITY_TYPES.items() if k in NER_MODELS[DEFAULT_NER_MODEL]["labels"]}
DEFAULT_TYPES = ["PER", "ORG", "LOC"]


def relationships_page():
    config = AppConfig()

    ui.label("Relationship Extraction").classes("text-h4")
    ui.label("Discover connections between entities in your documents").classes("text-subtitle1")
    ui.separator()

    with ui.card().classes("w-full"):
        input_dir = ui.input("Input Directory", value=config.get("defaults.relationships_input_dir", "")).classes("w-full")
        ui.button("Browse...", on_click=lambda: browse_dir(input_dir), icon="folder_open").props("flat")

    with ui.card().classes("w-full"):
        ui.label("Entity Types").classes("text-subtitle2")
        entity_select = ui.select(
            ENTITY_TYPES,
            multiple=True,
            label="Select entity types",
            value=[t for t in config.get("defaults.relationships_types", DEFAULT_TYPES) if t in ENTITY_TYPES],
        ).classes("w-full")
        ui.label(
            "Entities come from the multilingual NER model (Downloads page). The Relationship"
            " column lists the words connecting each pair of entities in a sentence."
        ).classes("text-caption text-grey")

    with ui.card().classes("w-full"):
        with ui.row():
            extract_text = ui.checkbox("Extract text from PDFs", value=False)
            generate_graph = ui.checkbox("Generate network graph", value=True)
        ui.label(
            "\"Extract text from PDFs\" extracts raw text from PDF files before processing."
            " Leave unchecked if your input directory already contains plain text files."
        ).classes("text-caption text-grey")

    progress = ui.linear_progress(show_value=False).props("indeterminate").classes("w-full")
    progress.set_visibility(False)
    status_label = ui.label("Ready")

    async def run_extraction():
        in_dir = input_dir.value
        if not in_dir or not os.path.isdir(in_dir):
            ui.notify("Please select a valid input directory.", type="warning")
            return
        if not entity_select.value:
            ui.notify("Please select at least one entity type.", type="warning")
            return

        progress.set_visibility(True)
        status_label.set_text("Loading NER model (downloads ~182 MB on first use) and extracting relationships...")

        def do_extract():
            from NLP.relationship_extraction import process_files_for_relationships
            return process_files_for_relationships(
                input_dir=in_dir,
                output_dir=in_dir,
                model_name="detailed",
                extract_text=1 if extract_text.value else 0,
                generate_graph=1 if generate_graph.value else 0,
                entity_types=entity_select.value,
            )

        try:
            results = await run.io_bound(do_extract)

            if results["status"] == "success":
                msg = f"Found {results['relationship_count']} relationships across {results['file_count']} files."
                status_label.set_text(msg)
                ui.notify(msg, type="positive")
            elif results["status"] == "warning":
                status_label.set_text(results["message"])
                ui.notify(results["message"], type="warning")
            else:
                status_label.set_text(results["message"])
                ui.notify(results["message"], type="negative")
        except ImportError as e:
            status_label.set_text(f"Missing dependency: {e}")
            ui.notify(f"Missing dependency: {e}", type="negative")
        except Exception as e:
            status_label.set_text(f"Error: {e}")
            ui.notify(f"Extraction error: {e}", type="negative")
        finally:
            progress.set_visibility(False)

        config.set("defaults.relationships_input_dir", in_dir)
        config.set("defaults.relationships_types", entity_select.value)
        config.set("last_page", "/relationships")
        config.save()

    ui.button("Extract Relationships", on_click=run_extraction, icon="play_arrow").props("color=primary")
