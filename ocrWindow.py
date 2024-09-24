#!/usr/bin/python3
import os
import shutil
import tkinter as tk
import ocrmypdf
import pygubu

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'ocrWindow.ui')

tesseractLanguages = {
    "Afrikaans": "afr",
    "Albanian": "sqi",
    "Amharic": "amh",
    "Arabic (Script)": "Arabic",
    "Arabic": "ara",
    "Armenian (Script)": "Armenian",
    "Armenian": "hye",
    "Assamese": "Assamese",
    "Azerbaijani - Cyrillic": "aze_cyrl",
    "Azerbaijani": "aze",
    "Basque": "eus",
    "Belarusian": "bel",
    "Bengali (Script)": "Bengali",
    "Bengali": "ben",
    "Bosnian": "bos",
    "Breton": "bre",
    "Bulgarian": "bul",
    "Burmese": "mya",
    "Canadian Aboriginal (Script)": "Canadian_Aboriginal",
    "Catalan/Valencian": "cat",
    "Cebuano": "ceb",
    "Central Khmer": "khm",
    "Cherokee (Script)": "Cherokee",
    "Cherokee": "chr",
    "Chinese Simplified": "chi_sim",
    "Chinese Traditional": "chi_tra",
    "Corsican": "cos",
    "Croatian": "hrv",
    "Cyrillic (Script)": "Cyrillic",
    "Czech": "ces",
    "Danish": "dan",
    "Devanagari (Script)": "Devanagari",
    "Dhivehi": "div",
    "Dutch/Flemish": "nld",
    "Dzongkha": "dzo",
    "English": "eng",
    "English, Middle, 1100-1500": "enm",
    "Esperanto": "epo",
    "Estonian": "est",
    "Ethiopic (Script)": "Ethiopic",
    "Faroese": "fao",
    "Filipino": "fil",
    "Finnish": "fin",
    "Fraktur (Script)": "Fraktur",
    "French": "fra",
    "French, Middle, ca.1400-1600": "frm",
    "Galician": "glg",
    "Georgian (Script)": "Georgian",
    "Georgian - Old": "kat_old",
    "Georgian": "kat",
    "German Fraktur Latin": "deu_latf",
    "German": "deu",
    "Greek (Script)": "Greek",
    "Greek, Ancient, to 1453": "grc",
    "Greek, Modern, 1453-": "ell",
    "Gujarati (Script)": "Gujarati",
    "Gujarati": "guj",
    "Gurmukhi (Script)": "Gurmukhi",
    "Haitian/Haitian Creole": "hat",
    "Han Simplified (Script)": "HanS",
    "Han Simplified - Vertical (Script)": "HanS_vert",
    "Han Traditional (Script)": "HanT",
    "Han Traditional - Vertical (Script)": "HanT_vert",
    "Hangul (Script)": "Hangul",
    "Hangul - Vertical (Script)": "Hangul_vert",
    "Hebrew (Script)": "Hebrew",
    "Hebrew": "heb",
    "Hindi": "hin",
    "Hungarian": "hun",
    "Icelandic": "isl",
    "Indonesian": "ind",
    "Inuktitut": "iku",
    "Irish": "gle",
    "Italian - Old": "ita_old",
    "Italian": "ita",
    "Japanese (Script)": "Japanese",
    "Japanese - Vertical (Script)": "Japanese_vert",
    "Japanese": "jpn",
    "Javanese": "jav",
    "Kannada (Script)": "Kannada",
    "Kannada": "kan",
    "Kazakh": "kaz",
    "Khmer (Script)": "Khmer",
    "Kirghiz/Kyrgyz": "kir",
    "Korean Vertical": "kor_vert",
    "Korean": "kor",
    "Kurdish Kurmanji": "kmr",
    "Lao (Script)": "Lao",
    "Lao": "lao",
    "Latin (Script)": "Latin",
    "Latin": "lat",
    "Latvian": "lav",
    "Lithuanian": "lit",
    "Luxembourgish": "ltz",
    "Macedonian": "mkd",
    "Malay": "msa",
    "Malayalam (Script)": "Malayalam",
    "Malayalam": "mal",
    "Maltese": "mlt",
    "Maori": "mri",
    "Marathi": "mar",
    "Math Equations": "equ",
    "Mongolian": "mon",
    "Myanmar (Script)": "Myanmar",
    "Nepali": "nep",
    "Norwegian": "nor",
    "Occitan, 1500-": "oci",
    "Odia (Script)": "Odia",
    "Oriya": "ori",
    "Panjabi/Punjabi": "pan",
    "Persian": "fas",
    "Polish": "pol",
    "Portuguese": "por",
    "Pushto/Pashto": "pus",
    "Quechua": "que",
    "Romanian/Moldavian/Moldovan": "ron",
    "Russian": "rus",
    "Sanskrit": "san",
    "Scottish Gaelic": "gla",
    "Serbian - Latin": "srp_latn",
    "Serbian": "srp",
    "Sindhi": "snd",
    "Sinhala (Script)": "Sinhala",
    "Sinhala/Sinhalese": "sin",
    "Slovak": "slk",
    "Slovenian": "slv",
    "Spanish/Castilian": "spa",
    "Spanish/Old Castilian": "spa_old",
    "Sundanese": "sun",
    "Swahili": "swa",
    "Swedish": "swe",
    "Syriac (Script)": "Syriac",
    "Syriac": "syr",
    "Tajik": "tgk",
    "Tamil (Script)": "Tamil",
    "Tamil": "tam",
    "Tatar": "tat",
    "Telugu (Script)": "Telugu",
    "Telugu": "tel",
    "Thaana (Script)": "Thaana",
    "Thai (Script)": "Thai",
    "Thai": "tha",
    "Tibetan (Script)": "Tibetan",
    "Tibetan": "bod",
    "Tigrinya": "tir",
    "Tonga": "ton",
    "Turkish": "tur",
    "Uighur/Uyghur": "uig",
    "Ukrainian": "ukr",
    "Urdu": "urd",
    "Uzbek - Cyrilic": "uzb_cyrl",
    "Uzbek": "uzb",
    "Vietnamese (Script)": "Vietnamese",
    "Vietnamese": "vie",
    "Welsh": "cym",
    "West Frisian": "fry",
    "Yiddish": "yid",
    "Yoruba": "yor"
}


class ocrWindow:
    def __init__(self, master=None):
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)
        builder.add_from_file(PROJECT_UI)
        # Main widget
        self.ocrWindow: tk.Toplevel = builder.get_object("ocrWindow", master)
        # Create element references
        self.aboutDialog = builder.get_object("aboutDialog", self.ocrWindow)
        self.licenseDialog = builder.get_object("licenseDialog", self.ocrWindow)
        self.helpDialog = builder.get_object("helpDialog", self.ocrWindow)
        self.langListbox = builder.get_object("langSelection_Listbox", self.ocrWindow)
        self.PDFInputDir = builder.get_object("PDFInputDir", self.ocrWindow)
        self.PDFOutputDir = builder.get_object("PDFOutputDir", self.ocrWindow)
        self.PDFACheckbox = builder.get_object("PDFA_Checkbox", self.ocrWindow)
        self.rotatePagesCheckbox = builder.get_object("rotatePages_Checkbox", self.ocrWindow)
        self.deskewCheckbox = builder.get_object("deskew_Checkbox", self.ocrWindow)
        self.textFileCheckbox = builder.get_object("extractToTextFile_Checkbox", self.ocrWindow)
        self.redoOCRCheckbox = builder.get_object("redoOCR_Checkbox", self.ocrWindow)
        self.runOCRButton = builder.get_object("button_run_ocr", self.ocrWindow)
        self.progressBar = builder.get_object("progressBar", self.ocrWindow)
        # Insert langs into listbox
        for lang in tesseractLanguages.keys():
            self.langListbox.insert("end", lang)
        # Main menu
        _main_menu = builder.get_object("menu1", self.ocrWindow)
        self.ocrWindow.configure(menu=_main_menu)
        builder.connect_callbacks(self)

    def on_runOCR_item_clicked(self):
        # Generate list of needed language data
        pdfLanguageKeys = [self.langListbox.get(sel) for sel in self.langListbox.curselection()]
        pdfLanguageVals = [tesseractLanguages.get(i) for i in pdfLanguageKeys]
        pdfLanguageValsString = '+'.join(pdfLanguageVals)
        # Get user input vars
        pdfInputDir = self.PDFInputDir.cget('path')
        pdfOutputDir = self.PDFOutputDir.cget('path')
        PDFACheckboxState = self.builder.get_variable('PDFACheckboxState').get()  # 0 = unchecked; 1 = checked
        rotatePagesCheckboxState = self.builder.get_variable(
            'rotatePagesCheckboxState').get()  # 0 = unchecked; 1 = checked
        deskewCheckboxState = self.builder.get_variable('deskewCheckboxState').get()  # 0 = unchecked; 1 = checked
        textFileCheckboxState = self.builder.get_variable('textFileCheckboxState').get()  # 0 = unchecked; 1 = checked
        redoOCRCheckboxState = self.builder.get_variable('redoOCRCheckboxState').get()  # 0 = unchecked; 1 = checked
        # Get a list of all files in input dir
        filesInInputDir = []
        try:
            for dirPath, dirNames, filenames in os.walk(pdfInputDir):
                filesInInputDir.extend([os.path.join(dirPath, filename) for filename in filenames])
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck PDFs and retry."
            print(error)
        # Get a list of PDFs in input dir
        pdfsInInputDir = []
        for i in filesInInputDir:
            if i.endswith('.pdf'):
                pdfsInInputDir.append(str(i))

        # Duplicate folder structure of input folder to output folder without copying files
        def shutilsIgnoreFiles(dir, files):
            return [f for f in files if os.path.isfile(os.path.join(dir, f))]

        try:
            outputDirMDMT = os.path.join(pdfOutputDir, 'MDMT-OCR-Output')
            if os.path.exists(outputDirMDMT) and os.path.isdir(outputDirMDMT):
                shutil.rmtree(outputDirMDMT)
            shutil.copytree(pdfInputDir, outputDirMDMT, ignore=shutilsIgnoreFiles)
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nDelete and recreate output directory then retry."
            print(error)
        # Set Tesseract env. variable for tessdata path (system agnostic)
        os.environ["TESSDATA_PREFIX"] = os.path.join(PROJECT_PATH, 'OCR', 'tessdata')
        # Set tessconfigs path (system agnostic)
        tesseractConfig = os.path.join(PROJECT_PATH, 'OCR', 'tessdata', 'tessconfigs')
        # OCR the PDF using OCRmyPDF
        for i in pdfsInInputDir:
            try:
                inputDirStructure = os.path.relpath(i, pdfInputDir)
                outputDirPreserveStructure = os.path.join(pdfOutputDir, 'MDMT-OCR-Output', inputDirStructure)
                if bool(PDFACheckboxState) == True:
                    ocrmypdf.ocr(i, outputDirPreserveStructure,
                                 language=pdfLanguageValsString,
                                 tesseract_config=tesseractConfig,
                                 redo_ocr=bool(redoOCRCheckboxState),
                                 deskew=bool(deskewCheckboxState),
                                 rotate_pages=bool(rotatePagesCheckboxState),
                                 invalidate_digital_signatures=True)
                elif bool(PDFACheckboxState) == False:
                    ocrmypdf.ocr(i, outputDirPreserveStructure,
                                 language=pdfLanguageValsString,
                                 tesseract_config=tesseractConfig,
                                 redo_ocr=bool(redoOCRCheckboxState),
                                 deskew=bool(deskewCheckboxState),
                                 rotate_pages=bool(rotatePagesCheckboxState),
                                 output_type="pdf",
                                 invalidate_digital_signatures=True)
            except Exception as e:
                error = "ERROR: " + str(e) + ".\nCheck PDF inputs and retry."
                print(error)

    def on_quit_item_clicked(self):
        # Quit on exit
        self.ocrWindow.destroy()

    def on_about_item_clicked(self):
        # Open the "About PDF Analytics" window
        self.aboutDialog.run()

    def on_help_item_clicked(self):
        self.helpDialog.run()

    def on_viewLicenses_item_clicked(self):
        # Open the license terms text window
        self.licenseDialog.run()

    def run(self):
        self.ocrWindow.mainloop()


if __name__ == "__main__":
    app = ocrWindow()
    app.run()
