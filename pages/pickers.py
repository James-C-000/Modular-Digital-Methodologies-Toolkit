"""Folder and file pickers.

Windows and macOS run MDMT in a native pywebview window and use the operating
system's dialogs.  Linux runs MDMT in the user's browser, where a page cannot
see the server's file system, so it uses an in-app picker that browses the
local disk on the server side.  Pages use pick_folder()/pick_file() (usually
through pages.components.PathField) and never import webview themselves.
"""
import os
from pathlib import Path

from nicegui import app, ui

from common.ui_mode import use_native_window


async def pick_folder(start: str | None = None) -> str | None:
    if use_native_window():
        import webview
        result = await app.native.main_window.create_file_dialog(
            dialog_type=webview.FileDialog.FOLDER, allow_multiple=False, directory=_start_dir(start))
        return result[0] if result else None
    return await LocalFilePicker(start, mode="folder")


async def pick_file(start: str | None = None, extensions: list[str] | None = None,
                    description: str = "Files") -> str | None:
    if use_native_window():
        import webview
        file_types = (f"{description} ({';'.join('*' + e for e in extensions)})",) if extensions else ()
        result = await app.native.main_window.create_file_dialog(
            dialog_type=webview.FileDialog.OPEN, allow_multiple=False, directory=_start_dir(start),
            file_types=file_types)
        return result[0] if result else None
    return await LocalFilePicker(start, mode="file", extensions=extensions)


def _start_dir(start: str | None) -> str:
    if start:
        p = Path(start).expanduser()
        if p.is_file():
            p = p.parent
        if p.is_dir():
            return str(p)
    return str(Path.home())


class LocalFilePicker(ui.dialog):
    """Server-side file/folder browser (based on NiceGUI's local_file_picker example).

    ``await LocalFilePicker(...)`` returns the chosen path, or None if cancelled.
    """

    def __init__(self, start: str | None, mode: str = "folder", extensions: list[str] | None = None):
        super().__init__()
        self.mode = mode
        self.extensions = tuple(e.lower() for e in (extensions or ()))
        self.path = Path(_start_dir(start))
        self.selected: Path | None = None
        self.show_hidden = False

        with self, ui.card().classes("w-[46rem] max-w-full"):
            ui.label("Choose a folder" if mode == "folder" else "Choose a file").classes("text-h6")
            self.crumbs = ui.row().classes("items-center gap-0 flex-wrap")
            with ui.row().classes("w-full items-center no-wrap"):
                self.path_input = ui.input("Path", value=str(self.path)).classes("flex-grow") \
                    .on("keydown.enter", lambda: self._go(self.path_input.value))
                ui.button(icon="arrow_upward", on_click=lambda: self._go(str(self.path.parent))) \
                    .props("flat dense").tooltip("Parent folder")
                ui.switch("Hidden", on_change=self._toggle_hidden).props("dense")
            if self.extensions:
                ui.label("Showing: " + ", ".join(self.extensions)).classes("text-caption text-grey")
            with ui.scroll_area().classes("w-full h-80 border rounded"):
                self.listing = ui.list().props("dense separator").classes("w-full")
            self.message = ui.label("").classes("text-caption text-negative")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=lambda: self.submit(None)).props("flat")
                if mode == "folder":
                    ui.button("Select this folder", on_click=lambda: self.submit(str(self.path))).props("color=primary")
                else:
                    self.open_button = ui.button("Open", on_click=self._open_selected).props("color=primary")
                    self.open_button.disable()
        self._render()
        self.open()

    def _toggle_hidden(self, e):
        self.show_hidden = e.value
        self._render()

    def _go(self, target: str):
        p = Path(os.path.expanduser(target or ""))
        if p.is_file() and self.mode == "file":
            self.submit(str(p))
            return
        if not p.is_dir():
            self.message.set_text(f"Not a folder: {target}")
            return
        self.path, self.selected = p.resolve(), None
        self._render()

    def _open_selected(self):
        if self.selected is not None:
            self.submit(str(self.selected))

    def _select(self, p: Path):
        self.selected = p
        self.open_button.enable()
        self._render()

    def _entries(self):
        try:
            entries = list(self.path.iterdir())
        except OSError as e:
            self.message.set_text(f"Cannot read this folder: {e.strerror or e}")
            return [], []
        self.message.set_text("")
        if not self.show_hidden:
            entries = [p for p in entries if not p.name.startswith(".")]
        folders = sorted((p for p in entries if _is_dir(p)), key=lambda p: p.name.lower())
        # Folder mode lists files too (dimmed, not selectable) so users can see
        # what a folder contains before choosing it.
        files = sorted((p for p in entries if not _is_dir(p)
                        and (not self.extensions or p.suffix.lower() in self.extensions)),
                       key=lambda p: p.name.lower())
        return folders, files

    def _render(self):
        self.path_input.set_value(str(self.path))
        self.crumbs.clear()
        with self.crumbs:
            parts = [self.path, *self.path.parents][::-1]
            for i, part in enumerate(parts):
                name = part.name or str(part)
                ui.button(name, on_click=lambda p=part: self._go(str(p))).props("flat dense no-caps")
                if 0 < i < len(parts) - 1 or (i == 0 and part.name and len(parts) > 1):
                    ui.label(os.sep).classes("text-grey")
        self.listing.clear()
        folders, files = self._entries()
        with self.listing:
            for p in folders:
                with ui.item(on_click=lambda p=p: self._go(str(p))):
                    with ui.item_section().props("avatar"):
                        ui.icon("folder", color="amber")
                    ui.item_section(p.name)
            for p in files:
                if self.mode == "folder":
                    with ui.item().classes("text-grey"):
                        with ui.item_section().props("avatar"):
                            ui.icon("description", color="grey")
                        ui.item_section(p.name)
                    continue
                item = ui.item(on_click=lambda p=p: self._select(p))
                item.on("dblclick", lambda p=p: self.submit(str(p)))
                if p == self.selected:
                    item.classes("bg-primary text-white")
                with item:
                    with ui.item_section().props("avatar"):
                        ui.icon("description")
                    ui.item_section(p.name)
            if not folders and not files:
                ui.item("(empty)").classes("text-grey")


def _is_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False
