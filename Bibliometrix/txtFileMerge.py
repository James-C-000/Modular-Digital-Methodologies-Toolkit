import pathlib
import pandas as pd

WoSDir = pathlib.Path("./records/WoS")
ScopusDir = pathlib.Path("./records/Scopus")
PubmedDir = pathlib.Path("./records/Pubmed")
WoSFiles = []
ScopusFiles = []
PubmedFiles = []

for item in WoSDir.iterdir():
    if item.is_file():
        WoSFiles.append(item)

for item in ScopusDir.iterdir():
    if item.is_file():
        ScopusFiles.append(item)

for item in PubmedDir.iterdir():
    if item.is_file():
        PubmedFiles.append(item)

with open('WoS.txt', 'w') as WoSMergedFile:
    for item in WoSFiles:
        with open(item) as inputFile:
            for line in inputFile:
                WoSMergedFile.write(line)
            WoSMergedFile.write("\n")
WoSMergedFile.close()

ScopusMergedFile = pd.concat([pd.read_csv(f) for f in ScopusFiles], ignore_index=True)
ScopusMergedFile.to_csv('Scopus.csv')

with open('Pubmed.txt', 'w') as PubmedMergedFile:
    for item in PubmedFiles:
        with open(item) as inputFile:
            for line in inputFile:
                PubmedMergedFile.write(line)
            PubmedMergedFile.write("\n")
PubmedMergedFile.close()
