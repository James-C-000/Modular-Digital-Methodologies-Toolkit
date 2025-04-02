#!/usr/bin/python3
import os
import sys
import tkinter as tk
from tkinter import messagebox
import pygubu
import threading
import webbrowser

# Import the co-word analysis main function
from NLP.co_word_analysis import main as co_word_analysis_main

PROJECT_PATH = os.getcwd()
# In audioTranscriptionWindow.py, ocrWindow.py, etc.
if hasattr(sys, '_MEIPASS'):
    # Running from PyInstaller bundle
    PROJECT_PATH = sys._MEIPASS
    PROJECT_UI = os.path.join(PROJECT_PATH, 'coWordAnalysisWindow.ui')  # Replace with appropriate UI filename
else:
    # Running in development
    PROJECT_PATH = os.getcwd()
    PROJECT_UI = os.path.join(PROJECT_PATH, 'coWordAnalysisWindow.ui')  # Replace with appropriate UI filename


class coWordAnalysisWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)

        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("coWordAnalysisWindow", master)

        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)

        # Create element references
        self.inputDir = builder.get_object("inputDir", self.mainwindow)
        self.runButton = builder.get_object("button_run_coword", self.mainwindow)
        self.progressBar = builder.get_object("progressBar", self.mainwindow)

        # Optional checkboxes
        self.openResultsCheckbox = builder.get_object("openResultsCheckbox", self.mainwindow)

        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_run_coword_clicked(self):
        # Get user input vars
        inputDir = self.inputDir.cget('path')
        openResults = self.builder.get_variable('openResultsState').get()

        # Validate inputs
        if not inputDir:
            messagebox.showerror("Error", "Please select an input directory.")
            return

        if not os.path.isdir(inputDir):
            messagebox.showerror("Error", "The selected input directory does not exist.")
            return

        # Disable run button and start progress bar
        self.runButton.configure(state='disabled')
        self.progressBar.configure(mode='indeterminate')
        self.progressBar.start()

        # Start processing in a separate thread
        cowordThread = threading.Thread(
            target=self.process_files,
            args=(inputDir,),
            daemon=True
        )
        cowordThread.start()

    def process_files(self, directory):
        try:
            # Call the co-word analysis main function
            co_word_analysis_main(directory)

            # Determine summary file path
            summary_file = os.path.join(directory, "Co_Word_Analysis_Summary.html")

            # Show completion message and optionally open results
            if os.path.exists(summary_file):
                # Determine whether to open results based on checkbox
                openResults = self.builder.get_variable('openResultsState').get()

                self.mainwindow.after(0, lambda: messagebox.showinfo(
                    "Success",
                    f"Co-word Analysis completed successfully. Results are saved in {directory}."
                ))

                if openResults:
                    self.mainwindow.after(0, lambda: webbrowser.open(summary_file))
            else:
                self.mainwindow.after(0, lambda: messagebox.showinfo(
                    "Success",
                    f"Co-word Analysis completed. No summary file found."
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
    app = coWordAnalysisWindow()
    app.run()