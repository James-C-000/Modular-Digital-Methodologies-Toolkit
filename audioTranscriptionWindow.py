#!/usr/bin/python3
import os
import shutil
import time
import tkinter as tk
from tkinter import messagebox
import ocrmypdf
import pygubu
import threading
import whisper

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'audioTranscriptionWindow.ui')

class audioTranscriptionWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object(
            "audioTranscriptionWindow", master)
        # Create element references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)
        self.audioDir = builder.get_object("audioInputDir", self.mainwindow)
        self.runTranscribeButton = builder.get_object("button_run_transcribe", self.mainwindow)
        self.progressBar = builder.get_object("progressBar", self.mainwindow)
        # Get model
        self.modelSelection = builder.get_variable("modelSelection")
        # Main menu
        _main_menu = builder.get_object("menu1", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_transcribe_item_clicked(self):
        transcribeThread = threading.Thread(target=self.transcribeThread, daemon=True)
        transcribeThread.start()

    def transcribeThread(self):
        # Disable OCR Button
        self.runTranscribeButton.configure(state='disabled')
        # Start the progress bar
        self.progressBar.configure(mode='indeterminate')
        self.progressBar.start()
        # Set selected transcribe model
        modelSelection = self.modelSelection.get()
        model = whisper.load_model(modelSelection)
        # Get user input vars
        audioDir = self.audioDir.cget('path')
        # Get a list of all files in input dir
        filesInInputDir = []
        try:
            for dirPath, dirNames, filenames in os.walk(audioDir):
                filesInInputDir.extend([os.path.join(dirPath, filename) for filename in filenames])
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck files and retry."
            messagebox.showerror(title='Error', message=error)
        # Get a list of audio files in input dir
        audioInInputDir = []
        for i in filesInInputDir:
            acceptableFormats = ('.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm')
            if i.endswith(acceptableFormats):
                audioInInputDir.append(str(i))
        # transcribe audio using openai-whisper
        for i in audioInInputDir:
            try:
                transcription = model.transcribe(i)
                with open(i + '.txt', 'w') as output:
                    output.write(transcription["text"])
            except Exception as e:
                error = "ERROR: " + str(e) + ".\nCheck audio input and retry.\nNot a fatal error, continuing..."
                messagebox.showerror(title='Error', message=error)
        # Stop progress bar
        self.progressBar.configure(mode='determinate')  # Hide progress bar pip
        self.progressBar.stop()
        # Enable OCR Button
        self.runTranscribeButton.configure(state='normal')

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
    app = audioTranscriptionWindow()
    app.run()
