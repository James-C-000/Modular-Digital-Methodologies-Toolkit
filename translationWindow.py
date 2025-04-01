#!/usr/bin/python3
import os
import time
import tkinter as tk
from tkinter import messagebox
import pygubu
import threading
import pathlib
import re
import glob
import sys
import importlib.util

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'translationWindow.ui')

# Dictionary of language codes for translation APIs
TRANSLATION_PAIRS = {
    "English → Spanish": ("en", "es"),
    "English → French": ("en", "fr"),
    "English → German": ("en", "de"),
    "English → Italian": ("en", "it"),
    "English → Portuguese": ("en", "pt"),
    "English → Russian": ("en", "ru"),
    "English → Chinese": ("en", "zh"),
    "Spanish → English": ("es", "en"),
    "French → English": ("fr", "en"),
    "German → English": ("de", "en"),
    "Italian → English": ("it", "en"),
    "Portuguese → English": ("pt", "en"),
    "Russian → English": ("ru", "en"),
    "Chinese → English": ("zh", "en"),
}


class TranslationWindow:
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
        self.inputDir = builder.get_object("documentInputDir", self.mainwindow)
        self.outputDir = builder.get_object("documentOutputDir", self.mainwindow)
        self.runTranslationButton = builder.get_object("button_run_translation", self.mainwindow)
        self.progressBar = builder.get_object("progressBar", self.mainwindow)
        self.modelListbox = builder.get_object("modelSelection_Listbox", self.mainwindow)
        self.modelListboxScrollbar = builder.get_object("modelSelection_Scrollbar", self.mainwindow)

        # Link listbox with scrollbar
        self.modelListbox['yscrollcommand'] = self.modelListboxScrollbar.set
        self.modelListboxScrollbar['command'] = self.modelListbox.yview

        # Insert translation models into listbox
        for model in TRANSLATION_PAIRS.keys():
            self.modelListbox.insert("end", model)

        # Select first model by default
        self.modelListbox.selection_set(0)

        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

        # For storing the translator module type and instance
        self.translator_type = None  # 'googletrans' or 'deep_translator'
        self.translator = None
        self.translation_initialized = False

    def on_run_translation_clicked(self):
        translationThread = threading.Thread(target=self.translation_thread, daemon=True)
        translationThread.start()

    def initialize_translation_backend(self, source_lang, target_lang):
        """Initialize online translation API backend"""
        if self.translation_initialized and self.translator is not None:
            # If reusing an existing translator, check if we need to create a new one
            # for a different language pair
            if hasattr(self, 'source_lang') and hasattr(self, 'target_lang'):
                if self.source_lang == source_lang and self.target_lang == target_lang:
                    # Same language pair, we can reuse
                    return True
                else:
                    # Different language pair, we need to reinitialize
                    self.translation_initialized = False
                    self.translator = None

        # Try googletrans first
        try:
            if importlib.util.find_spec("googletrans"):
                from googletrans import Translator

                self.translator = Translator()
                self.translator_type = 'googletrans'
                self.source_lang = source_lang
                self.target_lang = target_lang
                self.translation_initialized = True

                # Test the translator to make sure it's working
                test_result = self.translator.translate("Test", src=source_lang, dest=target_lang)
                if not (test_result and hasattr(test_result, 'text') and test_result.text):
                    raise Exception("Translator returned empty result")

                print(f"Successfully initialized Google Translate from {source_lang} to {target_lang}")
                print(f"Test translation: 'Test' -> '{test_result.text}'")

                messagebox.showinfo("Translation Setup",
                                    "Using Google Translate API for translation.")
                return True
        except ImportError:
            messagebox.showinfo("Translation Setup",
                                "Googletrans not available. Trying alternative...")
        except Exception as e:
            print(f"Error initializing googletrans: {str(e)}")
            messagebox.showinfo("Translation Setup",
                                f"Error with Googletrans: {str(e)}\nTrying alternative...")

        # Try deep_translator as fallback
        try:
            if importlib.util.find_spec("deep_translator"):
                import deep_translator

                # Store language information
                self.source_lang = source_lang
                self.target_lang = target_lang

                # Choose the best translator from deep_translator options
                if hasattr(deep_translator, "GoogleTranslator"):
                    # Test if the language pair is supported
                    try:
                        self.translator = deep_translator.GoogleTranslator(source=source_lang, target=target_lang)
                        test_result = self.translator.translate("Test")
                        self.translator_type = 'deep_translator_google'
                        print(f"Successfully initialized Google DeepTranslator from {source_lang} to {target_lang}")
                        print(f"Test translation: 'Test' -> '{test_result}'")
                    except Exception as e:
                        print(f"GoogleTranslator error: {str(e)}")
                        raise e
                elif hasattr(deep_translator, "MyMemoryTranslator"):
                    try:
                        self.translator = deep_translator.MyMemoryTranslator(source=source_lang, target=target_lang)
                        test_result = self.translator.translate("Test")
                        self.translator_type = 'deep_translator_mymemory'
                        print(f"Successfully initialized MyMemory DeepTranslator from {source_lang} to {target_lang}")
                        print(f"Test translation: 'Test' -> '{test_result}'")
                    except Exception as e:
                        print(f"MyMemoryTranslator error: {str(e)}")
                        raise e
                elif hasattr(deep_translator, "LingueeTranslator"):
                    try:
                        # Linguee doesn't need source for some language pairs
                        try:
                            self.translator = deep_translator.LingueeTranslator(source=source_lang, target=target_lang)
                        except:
                            self.translator = deep_translator.LingueeTranslator(target=target_lang)
                        test_result = self.translator.translate("Test")
                        self.translator_type = 'deep_translator_linguee'
                        print(f"Successfully initialized Linguee DeepTranslator from {source_lang} to {target_lang}")
                        print(f"Test translation: 'Test' -> '{test_result}'")
                    except Exception as e:
                        print(f"LingueeTranslator error: {str(e)}")
                        raise e
                else:
                    raise ImportError("No suitable translator found in deep_translator package")

                self.translation_initialized = True

                messagebox.showinfo("Translation Setup",
                                    f"Using {self.translator_type} for translation.")
                return True
        except ImportError:
            pass
        except Exception as e:
            print(f"Error with deep_translator: {str(e)}")
            messagebox.showinfo("Translation Setup",
                                f"Error with deep_translator: {str(e)}")

        # If we get here, no translation API is available
        messagebox.showerror("Error",
                             "No translation API available. Please install one of:\n"
                             "- googletrans==4.0.0-rc1\n"
                             "- deep-translator\n")
        return False

    def translation_thread(self):
        # Disable translation button
        self.runTranslationButton.configure(state='disabled')

        # Start progress bar
        self.progressBar.configure(mode='indeterminate')
        self.progressBar.start()

        # Get selected translation model
        selected_indices = self.modelListbox.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "Please select a translation model")
            self.runTranslationButton.configure(state='normal')
            self.progressBar.stop()
            return

        selected_model_name = self.modelListbox.get(selected_indices[0])
        source_lang, target_lang = TRANSLATION_PAIRS[selected_model_name]

        # Get user input vars
        input_dir = self.inputDir.cget('path')
        output_dir = self.outputDir.cget('path')

        # Validate inputs
        if not input_dir or not output_dir:
            messagebox.showerror("Error", "Please select both input and output directories")
            self.runTranslationButton.configure(state='normal')
            self.progressBar.stop()
            return

        try:
            # Initialize translation backend
            if not self.initialize_translation_backend(source_lang, target_lang):
                self.runTranslationButton.configure(state='normal')
                self.progressBar.stop()
                return

            # Create output directory if it doesn't exist
            output_dir_mdmt = os.path.join(output_dir, "MDMT-Translation-Output")
            os.makedirs(output_dir_mdmt, exist_ok=True)

            # Get a list of all files in input dir
            input_files = []
            for file_path in glob.glob(os.path.join(input_dir, "**/*.*"), recursive=True):
                if file_path.lower().endswith(('.txt', '.pdf')):
                    input_files.append(file_path)

            if not input_files:
                messagebox.showinfo("Information", "No .txt or .pdf files found in the input directory")
                self.runTranslationButton.configure(state='normal')
                self.progressBar.stop()
                return

            # Switch to determinate mode for progress tracking
            self.progressBar.stop()
            self.progressBar.configure(mode='determinate')
            self.progressBar.configure(maximum=len(input_files))
            self.progressBar.configure(value=0)

            # Process each file
            for i, file_path in enumerate(input_files):
                try:
                    # Update progress bar
                    self.progressBar.configure(value=i)
                    self.mainwindow.update_idletasks()

                    # Determine output path
                    rel_path = os.path.relpath(file_path, input_dir)
                    output_path_dir = os.path.dirname(os.path.join(output_dir_mdmt, rel_path))
                    os.makedirs(output_path_dir, exist_ok=True)

                    file_base = os.path.splitext(os.path.basename(file_path))[0]
                    # Always use .txt extension regardless of source file type
                    translated_filename = f"{file_base}_{target_lang.upper()}_translated.txt"
                    output_file_path = os.path.join(output_path_dir, translated_filename)

                    # Extract text from file (regardless of type, we'll get just the text)
                    if file_path.lower().endswith('.pdf'):
                        text = self.extract_text_from_pdf(file_path)
                    else:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            text = f.read()

                    # Translate the text
                    translated_text = self.translate_text(text, source_lang, target_lang)

                    # Write to output file
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        f.write(translated_text)

                except Exception as e:
                    error_msg = f"Error processing file {file_path}: {str(e)}"
                    messagebox.showerror("Error", error_msg)
                    # Continue with next file

            # Complete the progress bar
            self.progressBar.configure(value=len(input_files))
            messagebox.showinfo("Success", f"Translation complete! Translated {len(input_files)} files.")

        except Exception as e:
            messagebox.showerror("Error", f"Translation failed: {str(e)}")

        finally:
            # Reset progress bar and enable button
            self.progressBar.stop()
            self.progressBar.configure(mode='determinate')
            self.runTranslationButton.configure(state='normal')

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF with multiple fallback options"""
        # Try pdftotext first (best quality)
        try:
            import pdftotext
            with open(pdf_path, "rb") as f:
                pdf = pdftotext.PDF(f)
            return "\n\n".join(pdf)
        except ImportError:
            # Try PyPDF2
            try:
                import PyPDF2
                text = []
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text.append(page.extract_text())
                return "\n".join(text)
            except ImportError:
                # Try another fallback with pikepdf
                try:
                    import pikepdf
                    import re

                    text = []
                    with pikepdf.open(pdf_path) as pdf:
                        for page in pdf.pages:
                            if 'Contents' in page:
                                content = page.Contents.read_bytes()
                                text.append(
                                    re.sub(rb'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', b'', content).decode('utf-8',
                                                                                                           errors='replace'))
                    return "\n".join(text)
                except ImportError:
                    raise Exception(
                        "No PDF extraction library available. Please install pdftotext, PyPDF2, or pikepdf.")

    def translate_text(self, text, source_lang, target_lang):
        """Translate text using the initialized translation backend"""
        if not text.strip():
            return ""

        if self.translator_type == 'googletrans':
            return self._translate_with_googletrans(text, source_lang, target_lang)
        elif self.translator_type.startswith('deep_translator_'):
            return self._translate_with_deep_translator(text)
        else:
            raise Exception("No translation backend initialized")

    def _translate_with_googletrans(self, text, source_lang, target_lang):
        """Translate text using googletrans"""
        # Map our language codes to ones used by Google Translate
        lang_map = {
            'en': 'en',
            'es': 'es',
            'fr': 'fr',
            'de': 'de',
            'it': 'it',
            'pt': 'pt',
            'ru': 'ru',
            'zh': 'zh-cn'
        }

        src = lang_map.get(source_lang, 'auto')
        dest = lang_map.get(target_lang, 'en')

        # Log translation parameters
        print(f"Translating from {src} to {dest} using googletrans")

        # Split text into paragraphs to translate in smaller chunks
        paragraphs = text.split('\n\n')
        translated_paragraphs = []

        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                try:
                    # Add a short delay to avoid rate limiting
                    if i > 0 and i % 5 == 0:  # Every 5 paragraphs
                        time.sleep(1.5)  # 1.5 second delay

                    # Perform translation
                    translated = self.translator.translate(paragraph, src=src, dest=dest)
                    if translated and hasattr(translated, 'text') and translated.text:
                        translated_paragraphs.append(translated.text)
                    else:
                        # If translation failed but didn't raise an exception
                        print(f"Warning: Empty translation result for paragraph: {paragraph[:50]}...")
                        translated_paragraphs.append(paragraph)  # Keep original
                except Exception as e:
                    print(f"Translation error with paragraph: {str(e)}")
                    # If a paragraph fails, try to translate it sentence by sentence
                    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                    translated_sentences = []

                    for j, sentence in enumerate(sentences):
                        if sentence.strip():
                            try:
                                # Add a short delay every few sentences
                                if j > 0 and j % 10 == 0:
                                    time.sleep(1.0)

                                translated = self.translator.translate(sentence, src=src, dest=dest)
                                if translated and hasattr(translated, 'text') and translated.text:
                                    translated_sentences.append(translated.text)
                                else:
                                    translated_sentences.append(sentence)  # Keep original
                            except:
                                # If sentence fails, keep it as is
                                translated_sentences.append(sentence)

                    translated_paragraphs.append(" ".join(translated_sentences))
            else:
                translated_paragraphs.append("")

        result = '\n\n'.join(translated_paragraphs)
        # Verify we actually got translated text
        if not result or result.strip() == text.strip():
            print("Warning: Translation result appears to be identical to input")

        return result

    def _translate_with_deep_translator(self, text):
        """Translate text using deep_translator"""
        # Split text into paragraphs to translate in smaller chunks
        paragraphs = text.split('\n\n')
        translated_paragraphs = []

        # Log translation parameters
        print(f"Translating using {self.translator_type}")

        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                try:
                    # Add a short delay to avoid rate limiting
                    if i > 0 and i % 5 == 0:  # Every 5 paragraphs
                        time.sleep(1.5)  # 1.5 second delay

                    # Different translators have slightly different APIs
                    if self.translator_type == 'deep_translator_google':
                        translated = self.translator.translate(paragraph)
                    elif self.translator_type == 'deep_translator_mymemory':
                        # MyMemory has a 500 character limit
                        if len(paragraph) > 500:
                            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                            translated_sentences = []

                            for j, sentence in enumerate(sentences):
                                if sentence.strip():
                                    # Add a short delay every few sentences
                                    if j > 0 and j % 10 == 0:
                                        time.sleep(1.0)

                                    try:
                                        translated_text = self.translator.translate(sentence)
                                        if translated_text:
                                            translated_sentences.append(translated_text)
                                        else:
                                            translated_sentences.append(sentence)
                                    except:
                                        translated_sentences.append(sentence)

                            translated = " ".join(translated_sentences)
                        else:
                            translated = self.translator.translate(paragraph)
                    else:  # linguee or other
                        translated = self.translator.translate(paragraph)

                    if translated:
                        translated_paragraphs.append(translated)
                    else:
                        # If translation failed but didn't raise an exception
                        print(f"Warning: Empty translation result for paragraph: {paragraph[:50]}...")
                        translated_paragraphs.append(paragraph)  # Keep original
                except Exception as e:
                    print(f"Translation error with paragraph: {str(e)}")
                    # If a paragraph fails, try to translate it sentence by sentence
                    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                    translated_sentences = []

                    for j, sentence in enumerate(sentences):
                        if sentence.strip():
                            # Add a short delay every few sentences
                            if j > 0 and j % 10 == 0:
                                time.sleep(1.0)

                            try:
                                if self.translator_type == 'deep_translator_google':
                                    translated_text = self.translator.translate(sentence)
                                elif self.translator_type == 'deep_translator_mymemory':
                                    if len(sentence) > 500:
                                        # If still too long, keep original
                                        translated_text = sentence
                                    else:
                                        translated_text = self.translator.translate(sentence)
                                else:
                                    translated_text = self.translator.translate(sentence)

                                if translated_text:
                                    translated_sentences.append(translated_text)
                                else:
                                    translated_sentences.append(sentence)
                            except:
                                translated_sentences.append(sentence)

                    translated_paragraphs.append(" ".join(translated_sentences))
            else:
                translated_paragraphs.append("")

        result = '\n\n'.join(translated_paragraphs)
        # Verify we actually got translated text
        if not result or result.strip() == text.strip():
            print("Warning: Translation result appears to be identical to input")

        return result

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
    app = TranslationWindow()
    app.run()