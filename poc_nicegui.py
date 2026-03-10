"""Proof of concept: NiceGUI + pywebview native window + file dialog + background task."""
import multiprocessing
try:
    multiprocessing.set_start_method('fork')
except RuntimeError:
    pass

import time
import webview
from nicegui import app, ui, run


async def select_file():
    """Open a native file dialog via pywebview proxy."""
    result = await app.native.main_window.create_file_dialog(
        dialog_type=webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=('All Files (*.*)',),
    )
    if result:
        file_label.set_text(f"Selected: {result[0]}")
    else:
        file_label.set_text("No file selected")


async def run_background_task():
    """Demonstrate run.io_bound with progress feedback."""
    progress.set_visibility(True)
    status.set_text("Processing...")
    button.disable()

    def slow_task():
        time.sleep(3)
        return "Task completed successfully!"

    result = await run.io_bound(slow_task)
    status.set_text(result)
    progress.set_visibility(False)
    button.enable()


ui.label("MDMT Proof of Concept").classes("text-h4")
ui.separator()

ui.button("Select File (Native Dialog)", on_click=select_file)
file_label = ui.label("No file selected")

ui.separator()

button = ui.button("Run Background Task", on_click=run_background_task)
progress = ui.linear_progress().props("indeterminate")
progress.set_visibility(False)
status = ui.label("Ready")

ui.run(native=True, title="MDMT PoC", window_size=(800, 500), reload=False)
