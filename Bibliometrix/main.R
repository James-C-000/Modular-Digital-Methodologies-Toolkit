library(bibliometrix)
library(openxlsx)

WoS_Data <- convert2df(file="./WoS.txt",
                       dbsource="wos",
                       format="plaintext")

Scopus_Data <- convert2df(file="./Scopus.csv",
			  dbsource="scopus",
			  format="csv")

Pubmed_Data <- convert2df(file="./Pubmed.txt",
			  dbsource="pubmed",
			  format="pubmed")

merged = mergeDbSources(WoS_Data, Scopus_Data, Pubmed_Data, remove.duplicated = TRUE)

if ("CR" %in% names(merged)) {
	merged$CR <- NULL
}

if ("CR_raw" %in% names(merged)) {
	names(merged)[names(merged) == "CR_raw"] <- "CR"
}

#save(merged, file = "mergedDataset.RData")
write.xlsx(merged, file = "mergedDataset.xlsx")
