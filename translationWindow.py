#!/usr/bin/python3
import os
import tkinter as tk
from tkinter import messagebox
import pygubu
import threading
import asyncio
import sys

# Make sure we can import the googletranslateWrapper.py module
PROJECT_PATH = os.getcwd()
sys.path.append(os.path.join(PROJECT_PATH, 'Translation'))

PROJECT_UI = os.path.join(PROJECT_PATH, 'translationWindow.ui')

# Dictionary mapping display names to language codes for Google Translate
LANGUAGE_CODES = {
    "Arabic": "ar",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Portuguese": "pt",
    "Russian": "ru",
    "Chinese Simplified": "zh-CN",
    "Chinese Traditional": "zh-TW",
    "Dutch": "nl",
    "Hindi": "hi",
    "Swedish": "sv",
    # Default (English) if nothing is selected
    "English": "en"
}


class translationWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)

        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("translationWindow", master)

        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)

        # Get UI elements
        self.translationInputDir = builder.get_object("translationInputDir", self.mainwindow)
        self.targetLanguageCombobox = builder.get_object("targetLanguageCombobox", self.mainwindow)
        self.outputSuffixEntry = builder.get_object("outputSuffixEntry", self.mainwindow)
        self.useExistingOutputCheckbox = builder.get_object("useExistingOutputCheckbox", self.mainwindow)
        self.runTranslateButton = builder.get_object("button_run_translate", self.mainwindow)
        self.progressBar = builder.get_object("progressBar", self.mainwindow)

        # Set up language combobox
        # First populate the combobox with values
        language_options = list(LANGUAGE_CODES.keys())
        self.targetLanguageCombobox['values'] = language_options

        # Set default to Spanish if it exists in the list, otherwise select the first item
        if "Spanish" in language_options:
            self.targetLanguageCombobox.set("Spanish")
        elif len(language_options) > 0:
            self.targetLanguageCombobox.set(language_options[0])

        # Set default suffix
        self.outputSuffixEntry.insert(0, "_translated")

        # Main menu
        _main_menu = builder.get_object("menu1", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)

        # Connect callbacks
        builder.connect_callbacks(self)

    def on_translate_item_clicked(self):
        # Get user input vars
        inputDir = self.translationInputDir.cget('path')
        targetLangDisplay = self.targetLanguageCombobox.get()
        suffix = self.outputSuffixEntry.get()
        useExistingOutput = self.builder.get_variable('useExistingOutputState').get()

        # Validate inputs
        if not inputDir:
            messagebox.showerror("Error", "Please select a directory containing documents to translate.")
            return

        if not os.path.isdir(inputDir):
            messagebox.showerror("Error", "The selected input directory does not exist.")
            return

        if not targetLangDisplay:
            messagebox.showerror("Error", "Please select a target language.")
            return

        if not suffix:
            suffix = "_translated"  # Default suffix if none provided

        # Get language code from display name
        targetLang = LANGUAGE_CODES.get(targetLangDisplay, "en")  # Default to English if not found

        # Confirm with user
        confirmMsg = f"Ready to translate documents in:\n{inputDir}\n\nTo: {targetLangDisplay}\n"
        if useExistingOutput:
            confirmMsg += f"\nTranslated files will be saved in the same directory with suffix '{suffix}'."
        else:
            confirmMsg += f"\nTranslated files will be saved in new subdirectories with suffix '{suffix}'."

        if not messagebox.askyesno("Confirm Translation", confirmMsg):
            return

        # Disable the translate button and start progress bar
        self.runTranslateButton.configure(state='disabled')
        self.progressBar.configure(mode='indeterminate')
        self.progressBar.start()

        # Start translation in a separate thread to avoid freezing the UI
        translationThread = threading.Thread(
            target=self.translate_documents,
            args=(inputDir, targetLang, suffix, useExistingOutput),
            daemon=True
        )
        translationThread.start()

    def translate_documents(self, inputDir, targetLang, suffix, useExistingOutput):
        try:
            # Import the translation module
            from Translation.googletranslateWrapper import translate_documents_async

            # Create an asyncio event loop that can be used by the thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Configure translation settings
            translation_settings = {
                "TARGET_LANG": targetLang,
                "SUFFIX": suffix,
                "DIRECTORY": inputDir,
                "MAX_CHARS": 5000  # Default chunk size for translation
            }

            # Run the translation
            loop.run_until_complete(translate_documents_async(translation_settings))
            loop.close()

            # Show completion message once done
            self.mainwindow.after(0, lambda: self.show_completion_message("Translation completed successfully!"))

        except Exception as e:
            error_message = f"Error during translation: {str(e)}"
            self.mainwindow.after(0, lambda: self.show_completion_message(error_message, is_error=True))
        finally:
            # Always re-enable the button and stop the progress bar
            self.mainwindow.after(0, self.reset_ui)

    def show_completion_message(self, message, is_error=False):
        if is_error:
            messagebox.showerror("Translation Error", message)
        else:
            messagebox.showinfo("Translation Complete", message)

    def reset_ui(self):
        self.progressBar.stop()
        self.progressBar.configure(mode='determinate')
        self.runTranslateButton.configure(state='normal')

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
    app = translationWindow()
    app.run()