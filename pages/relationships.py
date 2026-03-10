"""Relationship extraction page."""
import os
from nicegui import app, ui, run
from config import AppConfig

ENTITY_TYPES = ["PERSON", "ORGANIZATION", "GPE", "LOCATION", "FACILITY", "DATE", "TIME", "MONEY", "PERCENT"]


def relationships_page():
    config = AppConfig()

    ui.label("Relationship Extraction").classes("text-h4")
    ui.label("Discover connections between entities in your documents").classes("text-subtitle1")
    ui.separator()

    input_dir = ui.input("Input Directory").classes("w-full")
    ui.button("Browse...", on_click=lambda: _browse_dir(input_dir), icon="folder_open").props("flat")

    ui.label("Entity Types").classes("text-subtitle2 q-mt-md")
    entity_select = ui.select(
        ENTITY_TYPES,
        multiple=True,
        label="Select entity types",
        value=["PERSON", "ORGANIZATION", "GPE"],
    ).classes("w-full")

    with ui.row():
        extract_text = ui.checkbox("Extract text from PDFs", value=False)
        generate_graph = ui.checkbox("Generate network graph", value=True)

    ui.separator()

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
        status_label.set_text("Downloading NLP data (if needed) and extracting relationships...")

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

        config.set("last_page", "/relationships")
        config.save()

    ui.button("Extract Relationships", on_click=run_extraction, icon="play_arrow").props("color=primary")


async def _browse_dir(target_input):
    import webview
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.FOLDER_DIALOG,
        allow_multiple=False,
    )
    if result and len(result) > 0:
        target_input.set_value(result[0])
