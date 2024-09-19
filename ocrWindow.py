#!/usr/bin/python3
import os
import pathlib
import tkinter as tk
import ocrmypdf
import pygubu

PROJECT_PATH = pathlib.Path(__file__).parent
PROJECT_UI = PROJECT_PATH / "ocrWindow.ui"


class ocrWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("ocrWindow", master)
        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)
        # Main menu
        _main_menu = builder.get_object("menu1", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_runOCR_item_clicked(self):
        # Get working dir (system agnostic)
        cwd = os.getcwd()
        # Set Tesseract env. variable for tessdata path (system agnostic)
        os.environ["TESSDATA_PREFIX"] = os.path.join(cwd, 'OCR', 'tessdata')
        # Set tessconfigs path (system agnostic)
        tesseractConfig = os.path.join(cwd, 'OCR', 'tessdata', 'tessconfigs')
        # Set OCR'd file inputs and outputs (will eventually be removed and replaced with a file picker)
        ocrInput = os.path.join(cwd, 'OCR', 'input.pdf')
        ocrOutput = os.path.join(cwd, 'OCR', 'output.pdf')

        # OCR the PDF using OCRmyPDF
        ocrmypdf.ocr(ocrInput, ocrOutput,
                     tesseract_config=tesseractConfig,
                     invalidate_digital_signatures=True)

    def on_quit_item_clicked(self):
        # Quit on exit
        self.mainwindow.destroy()

    def on_about_item_clicked(self):
        # Open the "About PDF Analytics" window
        self.aboutDialog.run()

    def on_help_item_clicked(self):
        self.helpDialog.run()

    def on_viewLicenses_item_clicked(self):
        # Open the license terms text window
        self.licenseDialog.run()

    def run(self):
        self.mainwindow.mainloop()


if __name__ == "__main__":
    app = ocrWindow()
    app.run()