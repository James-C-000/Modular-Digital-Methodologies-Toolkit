#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import messagebox
import pygubu
import threading

# Import the relationship extraction logic script
from NLP.relationship_extraction import process_files_for_relationships

PROJECT_PATH = os.getcwd()
# In audioTranscriptionWindow.py, ocrWindow.py, etc.
if hasattr(sys, '_MEIPASS'):
    # Running from PyInstaller bundle
    PROJECT_PATH = sys._MEIPASS
    PROJECT_UI = os.path.join(PROJECT_PATH, 'relationshipExtractionWindow.ui')  # Replace with appropriate UI filename
else:
    # Running in development
    PROJECT_PATH = os.getcwd()
    PROJECT_UI = os.path.join(PROJECT_PATH, 'relationshipExtractionWindow.ui')  # Replace with appropriate UI filename


class relationshipExtractionWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)

        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("relationshipExtractionWindow", master)

        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)

        # Create element references
        self.inputDir = builder.get_object("inputDir", self.mainwindow)
        self.outputDir = self.inputDir
        self.extractTextCheckbox = builder.get_object("extractTextCheckbox", self.mainwindow)
        self.generateGraphCheckbox = builder.get_object("generateGraphCheckbox", self.mainwindow)
        self.entityTypeList = builder.get_object("entityTypeList", self.mainwindow)
        self.runButton = builder.get_object("button_run_extraction", self.mainwindow)
        self.progressBar = builder.get_object("progressBar", self.mainwindow)

        # Populate entity type listbox
        entity_types = ["PERSON", "ORGANIZATION", "GPE", "LOCATION", "FACILITY", "DATE", "TIME", "MONEY", "PERCENT"]
        for entity_type in entity_types:
            self.entityTypeList.insert("end", entity_type)

        # Configure multiple selection mode
        self.entityTypeList.configure(selectmode="multiple")

        # Default selections (Person, Organization, GPE)
        self.entityTypeList.selection_set(0)  # PERSON
        self.entityTypeList.selection_set(1)  # ORGANIZATION
        self.entityTypeList.selection_set(2)  # GPE

        # Configure default checkbox states
        self.builder.get_variable('generateGraphState').set(1)  # Enable graph generation by default

        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_run_extraction_clicked(self):
        # Get user input vars
        inputDir = self.inputDir.cget('path')
        outputDir = inputDir
        extractText = self.builder.get_variable('extractTextState').get()
        generateGraph = self.builder.get_variable('generateGraphState').get()

        # Get selected entity types
        selected_indices = self.entityTypeList.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "Please select at least one entity type.")
            return

        selected_entity_types = [self.entityTypeList.get(idx) for idx in selected_indices]

        # Validate inputs
        if not inputDir:
            messagebox.showerror("Error", "Please select an input directory.")
            return

        if not outputDir:
            messagebox.showerror("Error", "Please select an output directory.")
            return

        # Always use "detailed" NLTK processing
        modelName = "detailed"

        # Disable run button and start progress bar
        self.runButton.configure(state='disabled')
        self.progressBar.configure(mode='indeterminate')
        self.progressBar.start()

        # Start processing in a separate thread
        extractionThread = threading.Thread(
            target=self.process_files,
            args=(inputDir, outputDir, modelName, extractText, generateGraph, selected_entity_types),
            daemon=True
        )
        extractionThread.start()

    def process_files(self, inputDir, outputDir, modelName, extractText, generateGraph, entity_types):
        try:
            # Call the relationship extraction logic function
            results = process_files_for_relationships(
                input_dir=inputDir,
                output_dir=outputDir,
                model_name=modelName,
                extract_text=extractText,
                generate_graph=generateGraph,
                entity_types=entity_types
            )

            # Handle the results
            if results['status'] == 'success':
                if results['relationship_count'] > 0:
                    self.mainwindow.after(0, lambda: messagebox.showinfo(
                        "Success",
                        f"Extraction complete. Found {results['relationship_count']} relationships "
                        f"across {results['file_count']} files."
                    ))
                else:
                    self.mainwindow.after(0, lambda: messagebox.showinfo(
                        "Information",
                        "No relationships found in the specified files."
                    ))
            elif results['status'] == 'warning':
                self.mainwindow.after(0, lambda: messagebox.showwarning(
                    "Warning",
                    results['message']
                ))
            else:  # error
                self.mainwindow.after(0, lambda: messagebox.showerror(
                    "Error",
                    results['message']
                ))

        except Exception as e:
            self.mainwindow.after(0, lambda: messagebox.showerror(
                "Error",
                f"An error occurred: {str(e)}"
            ))
        finally:
            self.mainwindow.after(0, self.reset_ui)

    def reset_ui(self):
        """Reset UI elements after processing completes"""
        self.progressBar.stop()
        self.progressBar.configure(mode='determinate')
        self.runButton.configure(state='normal')

    def on_quit_item_clicked(self):
        # Quit on exit
        self.mainwindow.destroy()

    def on_about_item_clicked(self):
        # Open the "About MDMT" window
        self.aboutDialog.run()

    def on_help_item_clicked(self):
        self.helpDialog.run()

    def on_viewLicenses_item_clicked(self):
        # Open the license terms text window
        self.licenseDialog.run()

    def run(self):
        self.mainwindow.mainloop()


if __name__ == "__main__":
    app = relationshipExtractionWindow()
    app.run()