#
# Script to batch parse PDF input files and generate data analytics based on some input
# Written for the linux operating system, compatibility with others is not guaranteed
#
# DEPENDENCIES: matplotlib, pdftotext, pygubu
#
# v. 1.x: 2019-07-05
# v. 2.0: 2020-11-15
# v. 2.1: 2021-08-27
# v. 3.0: 2022-04-03
#
import os
import pathlib
import sys

import pygubu
from tkinter import messagebox
from Advanced_Keyword_Search.advancedKeywordSearchLogic import core_logic
import threading

PROJECT_PATH = pathlib.Path(__file__).parent

# Replace it with this code that will work in both development and PyInstaller environments
if hasattr(sys, '_MEIPASS'):
    # Running from PyInstaller bundle
    PROJECT_UI = os.path.join(sys._MEIPASS, 'aksWindow.ui')
else:
    # Running in development
    PROJECT_UI = os.path.join(PROJECT_PATH, 'aksWindow.ui')


class aksWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.mainwindow = builder.get_object("toplevel1", master)
        # Create vars for user input
        self.manualFilters = builder.get_object("manualFilters")
        self.manualKeywords = builder.get_object("manualKeywords")
        self.contextLength = builder.get_object("contextLengthEntry")
        self.PDFDir = builder.get_object("PDFDirPath")
        self.filterDir = builder.get_object("filterDirPath")
        self.keywordDir = builder.get_object("keywordDirPath")
        self.basicFilterCheckbox = builder.get_object("basicFilterCheckbox")
        self.outputPath = builder.get_object("outputDirPath")
        # Create dialog references
        self.aboutDialog = builder.get_object("aboutDialog", self.mainwindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.mainwindow)
        self.helpDialog = builder.get_object("helpDialog", self.mainwindow)
        # Create progress bar reference
        self.progressBar = builder.get_object("progressBar")
        # Main menu
        _main_menu = builder.get_object("menuBar", self.mainwindow)
        self.mainwindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

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

    def on_keywordFilePathChanged(self, event=None):
        # Enable/disable manual keyword entry depending on if a keyword file has been selected
        keywordPath = self.keywordDir.cget('path')
        manualKeywordEntry = self.builder.get_object('manualKeywords')

        if keywordPath != '':
            manualKeywordEntry.delete('1.0', 'end')
            self.manualKeywords.configure(bg='grey')
            self.manualKeywords.configure(state='disabled')
        else:
            self.manualKeywords.configure(bg='white')
            self.manualKeywords.configure(state='normal')

    def on_filterFilePathChanged(self, event=None):
        # Enable/disable manual filter entry depending on if a filter file has been selected
        filterPath = self.filterDir.cget('path')
        manualFilterEntry = self.builder.get_object('manualFilters')

        if filterPath != '':
            manualFilterEntry.delete('1.0', 'end')
            self.manualFilters.configure(bg='grey')
            self.manualFilters.configure(state='disabled')
        else:
            self.manualFilters.configure(bg='white')
            self.manualFilters.configure(state='normal')

    def on_manualKeywordEntry(self, event=None):
        # Enable/disable keyword file selection depending on if keywords have been entered manually
        manualKeywordState = self.manualKeywords.cget('state')
        manualKeywordEntry = self.manualKeywords.get('1.0', 'end-1c')

        # Disable the keyword file picker if manual keywords are entered
        if manualKeywordState == 'disabled':
            pass
        else:
            if manualKeywordEntry != '':
                self.keywordDir.configure(state='disabled')
            else:
                self.keywordDir.configure(state='normal')

    def on_manualFilterEntry(self, event=None):
        # Enable/disable filter file selection depending on if filters have been entered manually
        manualFilterState = self.manualFilters.cget('state')
        manualFilterEntry = self.manualFilters.get('1.0', 'end-1c')

        # Disable the filter file picker if manual filters are entered
        if manualFilterState == 'disabled':
            pass
        else:
            if manualFilterEntry != '':
                self.filterDir.configure(state='disabled')
            else:
                self.filterDir.configure(state='normal')

    def on_enter_manualFilters(self, event=None):
        # Clear the text box
        manualFilters = self.builder.get_object('manualFilters').get('1.0', 'end-1c')
        if manualFilters == '!\n@\n#\n$':
            self.manualFilters.configure(foreground='black')
            self.manualFilters.delete('1.0', 'end')
        else:
            pass

    def on_enter_manualKeywords(self, event=None):
        # Clear the text box
        manualKeywords = self.builder.get_object('manualKeywords').get('1.0', 'end-1c')
        if manualKeywords == 'Washington\nState\nRatify\nKentucky':
            self.manualKeywords.configure(foreground='black')
            self.manualKeywords.delete('1.0', 'end')
        else:
            pass

    def on_basicFilter_clicked(self):
        # Enable/disable filter files and manual entry depending on if basic filter is enabled (only letters, numbers)
        basicFilterState = self.builder.get_variable('basicFilterState').get()  # Check if basic filter is enabled
        manualFilterEntry = self.builder.get_object('manualFilters')
        filterPath = self.builder.get_object('filterDirPath')

        # Clear/disable user filters if basic filter is selected
        if basicFilterState == 1:
            manualFilterEntry.delete('1.0', 'end')
            filterPath.configure(path='')
            self.filterDir.configure(state='disabled')
            self.manualFilters.configure(state='disabled')
            self.manualFilters.configure(bg='grey')
        else:
            self.filterDir.configure(state='normal')
            self.manualFilters.configure(state='normal')
            self.manualFilters.configure(bg='white')

    def check_ContextLengthEntry(self, p_entry_value):
        if p_entry_value.isnumeric():
            return True
        elif p_entry_value == '':
            return True
        else:
            return False

    def check_AnalyzeButtonState(self):
        contextLength = self.builder.get_object('contextLengthEntry').get()  # Get context length
        basicFilterState = self.builder.get_variable('basicFilterState').get()  # Get if basic filter is enabled
        PDFDirectory = self.PDFDir.cget('path')  # Get PDF directory path
        outputDirectory = self.outputPath.cget('path')  # Get output directory path
        keywordFilePath = self.keywordDir.cget('path')  # Get keyword file path
        manualKeywords = self.builder.get_object('manualKeywords').get('1.0', 'end-1c')  # Get manual keywords
        filterFilePath = self.filterDir.cget('path')  # Get filter file path
        manualFilters = self.builder.get_object('manualFilters').get('1.0', 'end-1c')  # Get manual filters

        if contextLength != '' and (basicFilterState == 1 or filterFilePath != '' or manualFilters != ('' or '!\n@\n#\n$')) \
                and (keywordFilePath != '' or manualKeywords != ('' or 'Washington\nState\nRatify\nKentucky')) \
                and outputDirectory != '' and PDFDirectory != '':
            return True
        else:
            return False

    def on_analyze_item_clicked(self):

        def checkLogicThread():
            if not logicThread.is_alive():
                self.progressBar.stop()
                self.progressBar.configure(mode='determinate')  # Hacky way to hide pbar before logic code runs
            else:
                self.progressBar.step(2)  # Increase/decrease by 2px every 25ms
                self.mainwindow.after(25, checkLogicThread)

        # Actions taken after pressing the analyze button
        # USER INPUT VARS
        contextLength = self.builder.get_object('contextLengthEntry').get()  # Get context length
        basicFilterState = self.builder.get_variable('basicFilterState').get()  # Get if basic filter is enabled
        PDFDirectory = self.PDFDir.cget('path')  # Get PDF directory path
        outputDirectory = self.outputPath.cget('path')  # Get output directory path
        keywordFilePath = self.keywordDir.cget('path')  # Get keyword file path
        manualKeywords = self.builder.get_object('manualKeywords').get('1.0', 'end-1c')  # Get manual keywords
        filterFilePath = self.filterDir.cget('path')  # Get filter file path
        manualFilters = self.builder.get_object('manualFilters').get('1.0', 'end-1c')  # Get manual filters

        if PDFDirectory == outputDirectory:
            # Input cannot equal output, or else there will be a feedback loop
            messagebox.showerror(title='Error', message='Input and output directory cannot be the same')
        elif not self.check_AnalyzeButtonState():
            # Do not pass if missing required data
            messagebox.showerror(title='Error', message='Please enter all required fields')
        else:
            # Pass parameters into logic code here
            self.progressBar.configure(mode='indeterminate')  # Hacky way to hide pbar before logic code runs
            logicThread = threading.Thread(target=core_logic,
                                           args=(contextLength, basicFilterState, PDFDirectory, outputDirectory,
                                                 keywordFilePath, manualKeywords, filterFilePath, manualFilters),
                                           daemon=True)
            logicThread.start()
            checkLogicThread()

    def run(self):
        self.mainwindow.mainloop()


def logic_message(message):
    messagebox.showinfo(title='Information', message=message)


def logic_error(errorMessage):
    messagebox.showerror(title='Error', message=errorMessage)


if __name__ == "__main__":
    app = aksWindow()
    app.run()
