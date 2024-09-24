#!/usr/bin/python3
import os
import shutil
import tkinter as tk
import ocrmypdf
import pygubu

PROJECT_PATH = os.getcwd()
PROJECT_UI = os.path.join(PROJECT_PATH, 'ocrWindow.ui')

tesseractLanguages = {
    "Afrikaans": "afr.traineddata",
    "Albanian": "sqi.traineddata",
    "Amharic": "amh.traineddata",
    "Arabic (Script)": "Arabic.traineddata",
    "Arabic": "ara.traineddata",
    "Armenian (Script)": "Armenian.traineddata",
    "Armenian": "hye.traineddata",
    "Assamese": "Assamese.traineddata",
    "Azerbaijani - Cyrillic": "aze_cyrl.traineddata",
    "Azerbaijani": "aze.traineddata",
    "Basque": "eus.traineddata",
    "Belarusian": "bel.traineddata",
    "Bengali (Script)": "Bengali.traineddata",
    "Bengali": "ben.traineddata",
    "Bosnian": "bos.traineddata",
    "Breton": "bre.traineddata",
    "Bulgarian": "bul.traineddata",
    "Burmese": "mya.traineddata",
    "Canadian Aboriginal (Script)": "Canadian_Aboriginal.traineddata",
    "Catalan/Valencian": "cat.traineddata",
    "Cebuano": "ceb.traineddata",
    "Central Khmer": "khm.traineddata",
    "Cherokee (Script)": "Cherokee.traineddata",
    "Cherokee": "chr.traineddata",
    "Chinese Simplified": "chi_sim.traineddata",
    "Chinese Traditional": "chi_tra.traineddata",
    "Corsican": "cos.traineddata",
    "Croatian": "hrv.traineddata",
    "Cyrillic (Script)": "Cyrillic.traineddata",
    "Czech": "ces.traineddata",
    "Danish": "dan.traineddata",
    "Devanagari (Script)": "Devanagari.traineddata",
    "Dhivehi": "div.traineddata",
    "Dutch/Flemish": "nld.traineddata",
    "Dzongkha": "dzo.traineddata",
    "English": "eng.traineddata",
    "English, Middle, 1100-1500": "enm.traineddata",
    "Esperanto": "epo.traineddata",
    "Estonian": "est.traineddata",
    "Ethiopic (Script)": "Ethiopic.traineddata",
    "Faroese": "fao.traineddata",
    "Filipino": "fil.traineddata",
    "Finnish": "fin.traineddata",
    "Fraktur (Script)": "Fraktur.traineddata",
    "French": "fra.traineddata",
    "French, Middle, ca.1400-1600": "frm.traineddata",
    "Galician": "glg.traineddata",
    "Georgian (Script)": "Georgian.traineddata",
    "Georgian - Old": "kat_old.traineddata",
    "Georgian": "kat.traineddata",
    "German Fraktur Latin": "deu_latf.traineddata",
    "German": "deu.traineddata",
    "Greek (Script)": "Greek.traineddata",
    "Greek, Ancient, to 1453": "grc.traineddata",
    "Greek, Modern, 1453-": "ell.traineddata",
    "Gujarati (Script)": "Gujarati.traineddata",
    "Gujarati": "guj.traineddata",
    "Gurmukhi (Script)": "Gurmukhi.traineddata",
    "Haitian/Haitian Creole": "hat.traineddata",
    "Han Simplified (Script)": "HanS.traineddata",
    "Han Simplified - Vertical (Script)": "HanS_vert.traineddata",
    "Han Traditional (Script)": "HanT.traineddata",
    "Han Traditional - Vertical (Script)": "HanT_vert.traineddata",
    "Hangul (Script)": "Hangul.traineddata",
    "Hangul - Vertical (Script)": "Hangul_vert.traineddata",
    "Hebrew (Script)": "Hebrew.traineddata",
    "Hebrew": "heb.traineddata",
    "Hindi": "hin.traineddata",
    "Hungarian": "hun.traineddata",
    "Icelandic": "isl.traineddata",
    "Indonesian": "ind.traineddata",
    "Inuktitut": "iku.traineddata",
    "Irish": "gle.traineddata",
    "Italian - Old": "ita_old.traineddata",
    "Italian": "ita.traineddata",
    "Japanese (Script)": "Japanese.traineddata",
    "Japanese - Vertical (Script)": "Japanese_vert.traineddata",
    "Japanese": "jpn.traineddata",
    "Javanese": "jav.traineddata",
    "Kannada (Script)": "Kannada.traineddata",
    "Kannada": "kan.traineddata",
    "Kazakh": "kaz.traineddata",
    "Khmer (Script)": "Khmer.traineddata",
    "Kirghiz/Kyrgyz": "kir.traineddata",
    "Korean Vertical": "kor_vert.traineddata",
    "Korean": "kor.traineddata",
    "Kurdish Kurmanji": "kmr.traineddata",
    "Lao (Script)": "Lao.traineddata",
    "Lao": "lao.traineddata",
    "Latin (Script)": "Latin.traineddata",
    "Latin": "lat.traineddata",
    "Latvian": "lav.traineddata",
    "Lithuanian": "lit.traineddata",
    "Luxembourgish": "ltz.traineddata",
    "Macedonian": "mkd.traineddata",
    "Malay": "msa.traineddata",
    "Malayalam (Script)": "Malayalam.traineddata",
    "Malayalam": "mal.traineddata",
    "Maltese": "mlt.traineddata",
    "Maori": "mri.traineddata",
    "Marathi": "mar.traineddata",
    "Math Equations": "equ.traineddata",
    "Mongolian": "mon.traineddata",
    "Myanmar (Script)": "Myanmar.traineddata",
    "Nepali": "nep.traineddata",
    "Norwegian": "nor.traineddata",
    "Occitan, 1500-": "oci.traineddata",
    "Odia (Script)": "Odia.traineddata",
    "Oriya": "ori.traineddata",
    "Panjabi/Punjabi": "pan.traineddata",
    "Persian": "fas.traineddata",
    "Polish": "pol.traineddata",
    "Portuguese": "por.traineddata",
    "Pushto/Pashto": "pus.traineddata",
    "Quechua": "que.traineddata",
    "Romanian/Moldavian/Moldovan": "ron.traineddata",
    "Russian": "rus.traineddata",
    "Sanskrit": "san.traineddata",
    "Scottish Gaelic": "gla.traineddata",
    "Serbian - Latin": "srp_latn.traineddata",
    "Serbian": "srp.traineddata",
    "Sindhi": "snd.traineddata",
    "Sinhala (Script)": "Sinhala.traineddata",
    "Sinhala/Sinhalese": "sin.traineddata",
    "Slovak": "slk.traineddata",
    "Slovenian": "slv.traineddata",
    "Spanish/Castilian": "spa.traineddata",
    "Spanish/Old Castilian": "spa_old.traineddata",
    "Sundanese": "sun.traineddata",
    "Swahili": "swa.traineddata",
    "Swedish": "swe.traineddata",
    "Syriac (Script)": "Syriac.traineddata",
    "Syriac": "syr.traineddata",
    "Tajik": "tgk.traineddata",
    "Tamil (Script)": "Tamil.traineddata",
    "Tamil": "tam.traineddata",
    "Tatar": "tat.traineddata",
    "Telugu (Script)": "Telugu.traineddata",
    "Telugu": "tel.traineddata",
    "Thaana (Script)": "Thaana.traineddata",
    "Thai (Script)": "Thai.traineddata",
    "Thai": "tha.traineddata",
    "Tibetan (Script)": "Tibetan.traineddata",
    "Tibetan": "bod.traineddata",
    "Tigrinya": "tir.traineddata",
    "Tonga": "ton.traineddata",
    "Turkish": "tur.traineddata",
    "Uighur/Uyghur": "uig.traineddata",
    "Ukrainian": "ukr.traineddata",
    "Urdu": "urd.traineddata",
    "Uzbek - Cyrilic": "uzb_cyrl.traineddata",
    "Uzbek": "uzb.traineddata",
    "Vietnamese (Script)": "Vietnamese.traineddata",
    "Vietnamese": "vie.traineddata",
    "Welsh": "cym.traineddata",
    "West Frisian": "fry.traineddata",
    "Yiddish": "yid.traineddata",
    "Yoruba": "yor.traineddata"
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

    def shutilsIgnoreFiles(self, dir, files):
        return [f for f in files if os.path.isfile(os.path.join(dir, f))]

    def on_runOCR_item_clicked(self):
        # Generate list of needed language data
        pdfLanguageKeys = [self.langListbox.get(sel) for sel in self.langListbox.curselection()]
        pdfLanguageVals = [tesseractLanguages.get(i) for i in pdfLanguageKeys]
        # Get user input vars
        pdfInputDir = self.PDFInputDir.cget('path')
        pdfOutputDir = self.PDFOutputDir.cget('path')
        PDFACheckboxState = self.builder.get_variable('PDFACheckboxState').get()  # 0 = unchecked; 1 = checked
        rotatePagesCheckboxState = self.builder.get_variable('rotatePagesCheckboxState').get()  # 0 = unchecked; 1 = checked
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
        try:
            outputDirMDMT = os.path.join(pdfOutputDir, 'MDMT-OCR-Output')
            if os.path.exists(outputDirMDMT) and os.path.isdir(outputDirMDMT):
                shutil.rmtree(outputDirMDMT)
            shutil.copytree(pdfInputDir, outputDirMDMT, ignore=self.shutilsIgnoreFiles)
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
                print(tesseractConfig)
                ocrmypdf.ocr(i, outputDirPreserveStructure,
                             tesseract_config=tesseractConfig,
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