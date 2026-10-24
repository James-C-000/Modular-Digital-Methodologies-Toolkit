import re
import collections
import csv
import logging
import os
import unicodedata

from matplotlib.figure import Figure

from common.paths import unique_safe_filenames
from common.pdf_text import extract_pages

log = logging.getLogger(__name__)

# CSVs are opened by researchers in Excel: UTF-8 with a BOM so non-Latin text
# displays correctly, and newline="" so the csv module controls line endings
# (otherwise Windows gets a blank line after every row).
CSV_ENCODING = "utf-8-sig"


def basic_filter(text: str) -> str:
    """Keep letters of any script (with their accents, also as combining marks),
    digits and whitespace; drop punctuation, symbols and OCR noise."""
    return "".join(ch for ch in text if ch.isspace() or unicodedata.category(ch)[0] in "LMN")


def _save_pie(path, counts, labels, title):
    fig = Figure()
    ax = fig.subplots()
    ax.pie(counts, labels=labels, autopct=make_autopct(counts), radius=2.0)
    ax.set_title(title)
    ax.axis('equal')
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight')


def _save_bar(path, counts, labels, title, xlabel):
    fig = Figure()
    ax = fig.subplots()
    y_pos = list(range(len(labels)))
    ax.barh(y_pos, counts, align='center', alpha=0.5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Words')
    ax.set_title(title)
    ax.set_yticks(y_pos, labels)
    fig.savefig(path, bbox_inches='tight')


# Format values for the charts
def make_autopct(values):
    def my_autopct(pct):
        total = sum(values)
        val = int(round(pct * total / 100.0))
        return '{p:.2f}% ({v:d})'.format(p=pct, v=val)

    return my_autopct


def core_logic(contextLength, basicFilterState, PDFDirectory, outputDirectory, keywordFilePath,
               manualKeywords, filterFilePath, manualFilters,
               on_error=None, on_message=None, on_progress=None, cancel=None):
    """Count keywords in every PDF of PDFDirectory; write CSVs and charts to outputDirectory.

    on_progress(done, total, current_file) is called before each PDF; a set
    *cancel* event stops before the next one (totals cover the PDFs read).
    Returns {"files": PDFs read, "total": PDFs found, "charts": [total chart paths]},
    or None after reporting an error through on_error.
    """
    logic_error = on_error or print
    logic_message = on_message or print
    log.debug("keyword search: context=%s basic_filter=%s pdfs=%s out=%s keyword_file=%s filter_file=%s",
              contextLength, basicFilterState, PDFDirectory, outputDirectory, keywordFilePath, filterFilePath)
    # Get a list of files in the pdf directory
    try:
        pdfsInDirectory = sorted(f for f in os.listdir(PDFDirectory) if f.endswith('.pdf'))
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck PDFs and retry."
        logic_error(error)
        return

    # Get user keywords
    if keywordFilePath != '':
        try:
            userKeywords = open(keywordFilePath, "r", encoding="utf-8")
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck keywords file and retry."
            logic_error(error)
            return
    else:
        try:
            userKeywords = manualKeywords.splitlines()
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck keyword entry and retry."
            logic_error(error)
            return

    # Create a dictionary of keywords, one for current iteration and one for total
    dictOfKeywords = {}  # current iteration
    totalDictOfKeywords = {}  # running total

    # Populate the dictionaries with the keywords we are looking for
    try:
        for line in userKeywords:
            line = line.lower()
            dictOfKeywords.update({line.rstrip("\n"): 0})
            totalDictOfKeywords.update({line.rstrip("\n"): 0})
        # Clear unneeded vars from memory
        del line
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck keywords and retry."
        logic_error(error)
        return

    # Create a csv file for each keyword.  Keywords can contain characters
    # that are not allowed in Windows filenames, so map them to safe names.
    keywordFiles = {k: os.path.join(outputDirectory, f)
                    for k, f in unique_safe_filenames(dictOfKeywords, '.csv').items()}
    keywords = dictOfKeywords.keys()
    for key in keywords:
        try:
            with open(keywordFiles[key], mode='w', encoding=CSV_ENCODING, newline='') as keywordCSV:
                writer = csv.writer(keywordCSV)
                writer.writerow(['Year', 'Page', 'Context: ' + str(key)])
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return
    # Clear unneeded vars from memory
    del key
    del keywords

    # Write the csv descriptors (i.e. year and keyword) to the first row
    try:
        with open(os.path.join(outputDirectory, "Data_Overview.csv"), mode='w',
                  encoding=CSV_ENCODING, newline='') as csv_file:
            fieldNames = list(dictOfKeywords.keys())  # convert the dict descriptors into a list
            fieldNames.insert(0, "Year")  # manually insert 'year' into 0,0 as it is not in the dict
            writer = csv.writer(csv_file)
            writer.writerow(fieldNames)
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
        logic_error(error)
        return

    # Open each pdf in a for loop
    filesRead = 0
    for index, i in enumerate(pdfsInDirectory):
        if cancel is not None and cancel.is_set():
            break
        if on_progress:
            on_progress(index, len(pdfsInDirectory), str(i))
        filesRead += 1
        try:
            pageTexts = extract_pages(os.path.join(PDFDirectory, str(i)))
            numOfPages = len(pageTexts)  # Get number of pages in open pdf
        except Exception as e:
            error = "ERROR: " + str(e) + " in file: " + str(i) + ".\nCheck PDFs and retry."
            logic_error(error)
            return

        pageNumber = 0  # Set current page

        # Check for hits page by page
        for allText in pageTexts:
            # Running page number
            pageNumber += 1
            if not allText:
                continue  # Skip empty pages

            # Strip user filters from text
            if basicFilterState == 1:
                allText = basic_filter(allText)
            elif filterFilePath != '':
                # use the filter file to get filters
                try:
                    with open(filterFilePath, 'r', encoding='utf-8') as file:
                        userFilters = file.read().replace('\n', '')
                    translationTable = allText.maketrans('', '', userFilters)
                    allText = allText.translate(translationTable)
                except Exception as e:
                    error = "ERROR: " + str(e) + ".\nCheck filter file and retry."
                    logic_error(error)
                    return
            else:
                # use user's manual filters
                userFilters = manualFilters.replace('\n', '')
                translationTable = allText.maketrans('', '', userFilters)
                allText = allText.translate(translationTable)
            # Format the text into all lowercase
            allText = allText.lower()
            # Iterate through each keyword
            for k in dictOfKeywords:
                try:
                    foundWords = re.findall(r'\s' + k + r'\s', allText)  # Find the keyword in the text
                except Exception as e:
                    error = ("ERROR: " + str(e) + " in file: " + str(i) +
                             " with keyword: " + str(k) + " on page: " + str(pageNumber))
                    logic_error(error)
                    return
                numOfFoundWords = len(foundWords)
                if numOfFoundWords != 0:  # Only update the dict if there are keywords
                    valueOfKey = int(dictOfKeywords.get(k)) + numOfFoundWords
                    dictOfKeywords.update({k: valueOfKey})
                    valueOfLongTermKey = int(totalDictOfKeywords.get(k)) + numOfFoundWords
                    totalDictOfKeywords.update({k: valueOfLongTermKey})
                    # Write reference data for each keyword while we are checking for it
                    try:
                        with open(keywordFiles[k], mode='a', encoding=CSV_ENCODING, newline='') as keywordCSV:
                            writer = csv.writer(keywordCSV)
                            if k.find(' ') != -1 and k.find('-') == -1:  # Check if keyword has spaces AND no hyphens
                                # Split on any whitespace (not just spaces) so a keyword at a line end still gets context.
                                # NOTE: Words that continue onto the next page will not be picked up here
                                allTextFiltered = re.split(r'[-\s]', allText)  # Split allText based on space/hyphen
                                matchedK = k.split()  # Split our keyword based on whitespace
                                # Only iterate within allTextFiltered bounds
                                # Check if allTextFiltered contains our k sequence.
                                # If it does, change the first found index to the whole
                                # word (k), then remove the every other index to remove word repetition
                                flaggedIndicies = []
                                for l in range(len(allTextFiltered) - len(matchedK)):
                                    match = True
                                    startIndex = l
                                    for m in range(len(matchedK)):
                                        if l + m < len(allTextFiltered) and allTextFiltered[l + m] == matchedK[m]:
                                            pass  # Match continues
                                        else:
                                            match = False
                                            break
                                    if match == True:
                                        allTextFiltered[startIndex] = str(k)
                                        for m in range(1, len(matchedK)):
                                            # Flag every index after allTextFiltered entry point within k bounds
                                            if startIndex + m < len(allTextFiltered):
                                                flaggedIndicies.append(startIndex + m)
                                for n in sorted(flaggedIndicies, reverse=True):
                                    if n < len(allTextFiltered):
                                        del allTextFiltered[n]
                            elif k.find('-') == -1:  # If the keyword is unhyphenated, remove hyphens from text
                                allTextFiltered = re.split(r'[-\s]', allText)
                            else:  # If not, just split it into a list based on whitespace
                                allTextFiltered = allText.split()
                            # Concat keywords with spaces
                            # Iterate over each word in the list
                            for l in range(len(allTextFiltered)):
                                if allTextFiltered[l] == k:  # Check if current iteration matches keyword
                                    halfContextLength = round(int(contextLength) / 2)
                                    preKeyword = allTextFiltered[
                                                 max(0, l - halfContextLength):l]  # Extract words before
                                    postKeyword = allTextFiltered[l:min(l + halfContextLength,
                                                                        len(allTextFiltered))]  # Extract hit + post words
                                    snippet = preKeyword + postKeyword  # concat the context
                                    # Remove whitespace indices from context list
                                    if ' ' in snippet:
                                        while ' ' in snippet:
                                            snippet.remove(' ')
                                    formattedContext = ' '.join(
                                        [str(word) for word in snippet])  # Cast from list -> str
                                    writer.writerow([i, pageNumber, formattedContext])
                    except Exception as e:
                        error = "ERROR: " + str(e) + ".\nCheck keyword csv file and retry."
                        logic_error(error)
                        return

        # Write the findings to the CSV file
        try:
            with open(os.path.join(outputDirectory, 'Data_Overview.csv'), mode='a',
                      encoding=CSV_ENCODING, newline='') as csv_file:
                writer = csv.writer(csv_file)
                csvList = list(dictOfKeywords.values())
                csvList.insert(0, str(i))
                writer.writerow(csvList)
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return

        # Sort from smallest to largest for readability
        sortedDictOfKeywords = collections.OrderedDict(
            sorted(dictOfKeywords.items(), key=lambda kv: (kv[1], kv[0])))
        count = sortedDictOfKeywords.values()
        label = sortedDictOfKeywords.keys()

        # If there are no hits for a keyword, remove it from the chart
        for j in list(sortedDictOfKeywords):
            if sortedDictOfKeywords.get(j) == 0:
                sortedDictOfKeywords.pop(j)

        # Chart formatting
        title = "Count for PDF " + str(i) + "\nPage count (PDF): " + str(numOfPages)
        try:
            _save_pie(os.path.join(outputDirectory, str(i) + '-PIE.png'), list(count), list(label), title)
            _save_bar(os.path.join(outputDirectory, str(i) + '-BAR.png'), list(count), list(label), title,
                      'Word Count')
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return

        dictOfKeywords = dictOfKeywords.fromkeys(dictOfKeywords, 0)

    # If there are no hits for a keyword, remove it from the final chart
    for i in list(totalDictOfKeywords):
        if totalDictOfKeywords.get(i) == 0:
            totalDictOfKeywords.pop(i)

    # Sort from smallest to largest for readability
    sortedTotalDictOfKeywords = collections.OrderedDict(
        sorted(totalDictOfKeywords.items(), key=lambda kv: (kv[1], kv[0])))
    totalCount = sortedTotalDictOfKeywords.values()
    totalLabels = sortedTotalDictOfKeywords.keys()

    # Chart formatting
    try:
        _save_pie(os.path.join(outputDirectory, 'totalPie.png'), list(totalCount), list(totalLabels),
                  'Total word count for every PDF')
        _save_bar(os.path.join(outputDirectory, 'totalBar.png'), list(totalCount), list(totalLabels),
                  'Total word count for every PDF', 'Total Word Count')
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
        logic_error(error)
        return

    if on_progress:
        on_progress(filesRead, len(pdfsInDirectory), "")
    return {"files": filesRead, "total": len(pdfsInDirectory),
            "charts": [os.path.join(outputDirectory, 'totalBar.png'),
                       os.path.join(outputDirectory, 'totalPie.png')]}

    logic_message("Processing Complete")