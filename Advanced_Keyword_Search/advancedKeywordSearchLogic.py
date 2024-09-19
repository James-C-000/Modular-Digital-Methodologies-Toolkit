import pdftotext
import matplotlib
import matplotlib.pyplot as plt
import re
import collections
import csv
import os


# Format values for the charts
def make_autopct(values):
    def my_autopct(pct):
        total = sum(values)
        val = int(round(pct * total / 100.0))
        return '{p:.2f}% ({v:d})'.format(p=pct, v=val)

    return my_autopct


def core_logic(contextLength, basicFilterState, PDFDirectory, outputDirectory, keywordFilePath,
               manualKeywords, filterFilePath, manualFilters):
    from defaultWindow import logic_error
    from defaultWindow import logic_message
    # Turn off matplotlib interactive mode
    matplotlib.use('Agg')
    plt.ioff()
    # Get user input from the GUI and feed into logic code
    print("contextLength: " + contextLength)
    print("basicFilterState: " + str(basicFilterState))
    print("PDFDirectory: " + PDFDirectory)
    print("outputDirectory: " + outputDirectory)
    print("keywordFilePath: " + keywordFilePath)
    print("manualKeywords: " + manualKeywords)
    print("filterFilePath: " + filterFilePath)
    print("manualFilters: " + manualFilters)
    # Get a list of files in the pdf directory
    try:
        pdfsInDirectory = [f for f in os.listdir(PDFDirectory) if f.endswith('.pdf')]
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck PDFs and retry."
        logic_error(error)
        return

    # Get user keywords
    if keywordFilePath != '':
        try:
            userKeywords = open(keywordFilePath, "r")
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

    # Create a csv file for each keyword
    keywords = dictOfKeywords.keys()
    for key in keywords:
        try:
            with open(os.path.join(outputDirectory, str(key) + '.csv'), mode='w') as keywordCSV:
                writer = csv.writer(keywordCSV)
                writer.writerow(['Year', 'Page', 'Context: ' + str(key)])
                keywordCSV.close()
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return
    # Clear unneeded vars from memory
    del key
    del keywords

    # Write the csv descriptors (i.e. year and keyword) to the first row
    try:
        with open(os.path.join(outputDirectory, "Data_Overview.csv"), mode='w') as csv_file:
            fieldNames = list(dictOfKeywords.keys())  # convert the dict descriptors into a list
            fieldNames.insert(0, "Year")  # manually insert 'year' into 0,0 as it is not in the dict
            writer = csv.writer(csv_file)
            writer.writerow(fieldNames)
            csv_file.close()
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
        logic_error(error)
        return

    # Open each pdf in a for loop
    for i in pdfsInDirectory:
        try:
            with open(os.path.join(PDFDirectory, str(i)), "rb") as pdf:
                pdfInput = pdftotext.PDF(pdf)  # Open pdf
        except Exception as e:
            error = "ERROR: " + str(e) + " in file: " + str(i) + ".\nCheck PDFs and retry."
            logic_error(error)
            return

        numOfPages = len(pdfInput)  # Get number of pages in open pdf
        pageNumber = 0  # Set current page

        # Check for hits page by page
        for j in pdfInput:
            # Running page number
            pageNumber += 1
            # Extract text on current page into string
            allText = j
            # Strip user filters from text
            if basicFilterState == 1:
                # filter everything that isn't a letter, number, or space
                allText = re.sub(r'[^a-zA-Z0-9 ]', '', allText)
            elif filterFilePath != '':
                # use the filter file to get filters
                try:
                    with open(filterFilePath, 'r') as file:
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
                             " with keyword: " + str(k) + " on page: " + str(pageNumber) +
                             " on word: " + str(l))
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
                        with open(os.path.join(outputDirectory, str(k) + '.csv'), mode='a') as keywordCSV:
                            writer = csv.writer(keywordCSV)
                            if k.find(' ') != -1 and k.find('-') == -1:  # Check if keyword has spaces AND no hyphens
                                # NOTE: Words that continue onto the next page will not be picked up here
                                allTextFiltered = re.split('[- ]', allText)  # Split allText based on space/hyphen
                                matchedK = k.split()  # Split our keyword based on whitespace
                                # Only iterate within allTextFiltered bounds
                                # Check if allTextFiltered contains our k sequence.
                                # If it does, change the first found index to the whole
                                # word (k), then remove the every other index to remove word repetition
                                for l in range(len(allTextFiltered) - len(matchedK)):
                                    for m in range(len(matchedK)):
                                        if allTextFiltered[l + m] == matchedK[m]:
                                            match = True
                                            startIndex = l
                                        else:
                                            match = False
                                            break
                                    if match == True:
                                        allTextFiltered[startIndex] = str(k)
                                        flaggedIndicies = []
                                        for m in range(1, len(matchedK)):
                                            # Flag every index after allTextFiltered entry point within k bounds
                                            flaggedIndicies.append(startIndex + m)
                                for n in sorted(flaggedIndicies, reverse=True):
                                    del allTextFiltered[n]
                            elif k.find('-') == -1:  # If the keyword is unhyphenated, remove hyphens from text
                                allTextFiltered = re.split('[- ]', allText)
                            else:  # If not, just split it into a list based on whitespace
                                allTextFiltered = allText.split()
                            # Concat keywords with spaces
                            # Iterate over each word in the list
                            for l in range(len(allTextFiltered)):
                                if allTextFiltered[l] == k:  # Check if current iteration matches keyword
                                    halfContextLength = round(int(contextLength) / 2)
                                    preKeyword = allTextFiltered[(l - halfContextLength):l]  # Extract 15 words before
                                    postKeyword = allTextFiltered[l:(l + halfContextLength)]  # Extract hit + post 15
                                    snippet = preKeyword + postKeyword  # concat the context
                                    # Remove whitespace indices from context list
                                    if snippet.count(' ') > 0:
                                        snippet.remove(' ')
                                    formattedContext = ' '.join([str(i) for i in snippet])  # Cast from list -> str
                                    writer.writerow([i, pageNumber, formattedContext])
                            keywordCSV.close()
                    except Exception as e:
                        error = "ERROR: " + str(e) + ".\nCheck keyword csv file and retry."
                        logic_error(error)
                        return

        # Write the findings to the CSV file
        try:
            with open(os.path.join(outputDirectory, 'Data_Overview.csv'), mode='a') as csv_file:
                writer = csv.writer(csv_file)
                csvList = list(dictOfKeywords.values())
                csvList.insert(0, str(i))
                writer.writerow(csvList)
                csv_file.close()
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
        plt.pie(list(count), labels=list(label), autopct=make_autopct(list(count)), radius=2.0)
        plt.title("Count for PDF " + str(i) + "\nPage count (PDF): " + str(numOfPages))
        plt.axis('equal')
        plt.tight_layout()
        try:
            plt.savefig(os.path.join(outputDirectory, str(i) + '-PIE.png'), bbox_inches='tight')
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return
        plt.close()

        y_pos = [i for i, _ in enumerate(list(label))]
        plt.barh(y_pos, list(count), align='center', alpha=0.5)
        plt.xlabel('Word Count')
        plt.ylabel('Words')
        plt.title("Count for PDF " + str(i) + "\nPage count (PDF): " + str(numOfPages))
        plt.yticks(y_pos, list(label))
        try:
            plt.savefig(os.path.join(outputDirectory, str(i) + '-BAR.png'), bbox_inches='tight')
        except Exception as e:
            error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
            logic_error(error)
            return
        plt.close()

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
    plt.pie(totalCount, labels=totalLabels, autopct=make_autopct(totalCount), radius=2.0)
    plt.title('Total word count for every PDF')
    plt.axis('equal')
    plt.tight_layout()
    try:
        plt.savefig(os.path.join(outputDirectory, 'totalPie.png'), bbox_inches='tight')
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
        logic_error(error)
        return
    plt.close()

    y_pos = [i for i, _ in enumerate(totalLabels)]
    plt.barh(y_pos, totalCount, align='center', alpha=0.5)
    plt.xlabel('Total Word Count')
    plt.ylabel('Words')
    plt.title('Total word count for every PDF')
    plt.yticks(y_pos, totalLabels)
    try:
        plt.savefig(os.path.join(outputDirectory, 'totalBar.png'), bbox_inches='tight')
    except Exception as e:
        error = "ERROR: " + str(e) + ".\nCheck output directory and retry."
        logic_error(error)
        return
    plt.close()

    logic_message("Processing Complete")
