#!/usr/bin/python3
import os
import tkinter as tk
import pygubu

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'defaultWindow.ui')


class defaultWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.mainwindow: tk.Toplevel = builder.get_object("defaultWindow", master)
        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)
        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_ocr_item_clicked(self):
        pass

    def on_about_item_clicked(self):
        # Open the "About MDMT" window
        self.aboutDialog.run()

    def on_help_item_clicked(self):
        # Open the "Help" window
        self.helpDialog.run()

    def on_quit_item_clicked(self):
        # Quit on exit
        self.mainwindow.destroy()

    def on_viewLicenses_item_clicked(self):
        self.licenseDialog.run()

    def run(self):
        self.mainwindow.mainloop()


if __name__ == "__main__":
    app = defaultWindow()
    app.run()
