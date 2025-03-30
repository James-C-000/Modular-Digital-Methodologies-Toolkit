#!/usr/bin/env python3
r"""
Enrich exported bibliometric records by sequentially querying multiple APIs for metadata.
For each record (row) in the input Excel file, the script queries the APIs in strict priority order and fills in any metadata
fields that are empty or contain placeholder values (e.g., "none" or "nan"), but only for fields whose corresponding columns
already existed in the original input file.
The API priority order is:
    1. Scopus (if API key is provided)
    2. OpenAlex
    3. PubMed Central (PMC)
    4. PubMed
    5. NIH Open Citation Collection (NIH-OCC)
    6. Crossref (direct lookup only)
    7. Semantic Scholar

For example, if the input file does not include the publisher field (PU), the script will not query for it.
Other functionalities (such as updating the DI field with a DOI found in the AID column) are maintained.
A detailed log is written immediately to disk (with a filename based on the current epoch time) as the script processes each record.
After processing every 100 rows, the current DataFrame is written to disk using openpyxl's write‑only mode to create a checkpoint.
"""

import pandas as pd
import requests
import json
import xml.etree.ElementTree as ET
import re
import time
from openpyxl import Workbook

# =====================================================
# Global Configuration
# =====================================================
EMAIL = "your_email_here@email.com"  # Replace with your actual email address
SCOPUS_API_KEY = ""  # Supply your Scopus API key (or leave empty to skip Scopus)
INPUT_FILE = "./records/mergedDataset_testing.xlsx"
OUTPUT_FILE = "./records/mergedDatasetEnhanced.xlsx"
SEMANTIC_SCHOLAR_API_KEY = ""  # Supply your Semantic Scholar API key if available

# The log filename will be based on the current epoch time.
log_filename = f"log-{int(time.time())}.txt"

HEADERS = {
    "User-Agent": f"BibliometrixMetadataEnhancer/1.0 (mailto:{EMAIL})",
    "From": EMAIL,
    "Accept": "application/json"
}
if SEMANTIC_SCHOLAR_API_KEY:
    HEADERS["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

# Global cache for OpenAlex citation lookups.
openalex_cache = {}


# =====================================================
# Helper Function to Save DataFrame using openpyxl Write-Only Mode
# =====================================================
def save_to_excel(df, filename):
    """Save the entire DataFrame to an Excel file using openpyxl's write-only mode."""
    try:
        wb = Workbook(write_only=True)
        ws = wb.create_sheet()
        ws.append(list(df.columns))
        for _, row in df.iterrows():
            ws.append(row.tolist())
        wb.save(filename)
        print(f"Checkpoint saved to {filename}.")
    except Exception as e:
        print(f"Error saving checkpoint to {filename}: {e}")


# =====================================================
# Robust Network Functions
# =====================================================
def robust_get(url, **kwargs):
    """A robust wrapper around requests.get that catches transient errors and retries indefinitely."""
    while True:
        try:
            response = requests.get(url, **kwargs)
            return response
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.RequestException) as e:
            print(f"Error accessing {url}: {e}. Retrying in 30 seconds...")
            time.sleep(30)


def robust_json(url, max_retries=3, **kwargs):
    """Retrieve and decode JSON from a URL, retrying on decode errors."""
    retries = 0
    while retries < max_retries:
        response = robust_get(url, **kwargs)
        try:
            return response.json()
        except json.decoder.JSONDecodeError as e:
            retries += 1
            print(f"JSON decode error for {url}: {e} (attempt {retries}/{max_retries}). Retrying in 30 seconds...")
            time.sleep(30)
    print(f"Skipping {url} after {max_retries} failed JSON decode attempts.")
    return None


# =====================================================
# Legacy PII-to-DOI Conversion Function (Kept for Reference)
# =====================================================
def convert_pii_to_doi(pii):
    url = "https://api.crossref.org/works"
    params = {"query.bibliographic": pii, "rows": 5}
    data = robust_json(url, params=params, headers=HEADERS)
    if data and "message" in data and "items" in data["message"]:
        for item in data["message"]["items"]:
            doi_candidate = item.get("DOI", "")
            if doi_candidate and doi_candidate.startswith("10."):
                print(f"Converted PII {pii} to DOI {doi_candidate} via Crossref search.")
                return doi_candidate
    return None


# =====================================================
# Scopus Title-Based Query Function with Abstract Inclusion
# =====================================================
def query_scopus_by_title(title, abstract=None):
    """
    Query the Elsevier Scopus Search API using the title and optionally the abstract.
    Constructs a query such as:
        TITLE("your title") AND ABS("your abstract")
    to narrow down the search. Extracts the DOI from the first matching record and then calls
    query_scopus_metadata() with that DOI.
    """
    query_parts = [f'TITLE("{title}")']
    if isinstance(abstract, str):
        trimmed_abstract = abstract.strip()
        if trimmed_abstract:
            query_parts.append(f'ABS("{trimmed_abstract}")')
    query = " AND ".join(query_parts)

    url = "https://api.elsevier.com/content/search/scopus"
    params = {"query": query, "rows": 1}
    headers = HEADERS.copy()
    headers["X-ELS-APIKey"] = SCOPUS_API_KEY
    headers["Accept"] = "application/json"

    response = robust_get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        items = data.get("search-results", {}).get("entry", [])
        if items:
            doi_candidate = items[0].get("prism:doi", "")
            if doi_candidate:
                print(f"Found DOI {doi_candidate} from title/abstract search.")
                return query_scopus_metadata(doi_candidate, title)
        print("No valid result from Scopus title/abstract search.")
        return False, None
    else:
        print(f"[Scopus] Title/abstract search for '{title}' returned {response.status_code}.")
        return False, None


# =====================================================
# Scopus API Query Function
# =====================================================
def query_scopus_metadata(identifier, title=None):
    """
    Query the Elsevier Scopus Abstract Retrieval API using a DOI.
    If the provided identifier does not start with "10." (i.e. is likely a PII) and a title is available,
    then perform a title-based search instead.
    Returns a metadata dictionary with keys matching Bibliometrix field tags.
    """
    if not identifier.startswith("10."):
        if title and str(title).strip():
            print(f"Identifier '{identifier}' is not a valid DOI. Using title-based search: '{title}'")
            return query_scopus_by_title(title)
        else:
            print("No valid DOI or title provided for Scopus lookup.")
            return False, None

    url = f"https://api.elsevier.com/content/abstract/doi/{identifier}"
    headers = HEADERS.copy()
    headers["X-ELS-APIKey"] = SCOPUS_API_KEY
    headers["Accept"] = "application/json"
    response = robust_get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        core = data.get("abstracts-retrieval-response", {}).get("coredata", {})
        meta = {}
        meta["DOI"] = core.get("prism:doi", "")
        meta["title"] = core.get("dc:title", "")
        meta["container-title"] = core.get("prism:publicationName", "")
        meta["author"] = core.get("dc:creator", "")
        cover_date = core.get("prism:coverDate", "")
        meta["issued"] = cover_date[:4] if cover_date else ""
        meta["volume"] = core.get("prism:volume", "")
        meta["issue"] = core.get("prism:issueIdentifier", "")
        meta["page"] = core.get("prism:pageRange", "")
        meta["abstract"] = core.get("dc:description", "")
        return True, meta
    else:
        print(f"[Scopus] Lookup for DOI {identifier} returned {response.status_code}. Skipping.")
        return False, None


# =====================================================
# OpenAlex Citation Lookup and Reference Processing
# =====================================================
def get_openalex_citation(openalex_id):
    if openalex_id in openalex_cache:
        return openalex_cache[openalex_id]
    url = f"https://api.openalex.org/works/{openalex_id}"
    try:
        resp = robust_get(url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            authors = []
            for auth in data.get("authorships", []):
                author = auth.get("author", {})
                display_name = (author.get("display_name") or "").strip()
                if display_name:
                    authors.append(display_name.upper())
            authors_str = ", ".join(authors)
            title = (data.get("title") or "").strip()
            journal = ""
            if "host_venue" in data and data["host_venue"]:
                journal = (data["host_venue"].get("display_name") or "").strip().upper()
            volume = (data.get("volume") or "").strip()
            year = str(data.get("publication_year") or "").strip()
            citation_parts = []
            if authors_str:
                citation_parts.append(authors_str)
            if title:
                citation_parts.append(title)
            if journal:
                citation_parts.append(journal)
            if volume:
                citation_parts.append(volume)
            if year:
                citation_parts.append(f"({year})")
            citation = ", ".join(citation_parts)
            citation = clean_citation(citation)
            openalex_cache[openalex_id] = citation
            return citation
        else:
            return None
    except Exception as e:
        print(f"[OpenAlex Lookup] Error: {e}")
        return None


# =====================================================
# Helper Functions to Process Metadata Fields
# =====================================================
def clean_citation(citation):
    citation = re.sub(r'<[^>]+>', '', citation)
    citation = re.sub(r'^\s*\d+[\)\.]\s*', '', citation)
    return citation.strip()


def process_title(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def process_container_title(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def process_author(value):
    if isinstance(value, list):
        authors = []
        for author in value:
            if isinstance(author, dict):
                family = author.get("family", "")
                given = author.get("given", "")
                name = f"{family}, {given}".strip(", ")
                if name:
                    authors.append(name)
            else:
                authors.append(str(author))
        return "; ".join(authors)
    return value


def process_issued(value):
    try:
        if isinstance(value, dict) and "date-parts" in value:
            dparts = value["date-parts"]
            if isinstance(dparts, list) and dparts and dparts[0]:
                return dparts[0][0]
    except Exception:
        pass
    return ""


def process_page(value):
    if isinstance(value, str) and "-" in value:
        parts = value.split("-")
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    return value, ""


def process_ISSN(value):
    if isinstance(value, list):
        return ", ".join(value)
    return value


def process_reference(value):
    if isinstance(value, list):
        processed_refs = []
        for ref in value:
            if isinstance(ref, dict):
                if 'unstructured' in ref and ref['unstructured']:
                    citation = clean_citation(ref['unstructured'].strip())
                    processed_refs.append(citation)
                elif 'DOI' in ref and ref['DOI']:
                    citation = clean_citation(ref['DOI'].strip())
                    processed_refs.append(citation)
                else:
                    processed_refs.append(clean_citation(str(ref).strip()))
            elif isinstance(ref, str):
                rstr = ref.strip()
                if rstr.lower() in ("none", "nan"):
                    continue
                if rstr.startswith("https://openalex.org/"):
                    openalex_id = rstr.replace("https://openalex.org/", "").strip()
                    citation = get_openalex_citation(openalex_id)
                    if citation:
                        processed_refs.append(citation)
                    else:
                        processed_refs.append(clean_citation(rstr))
                else:
                    processed_refs.append(clean_citation(rstr))
            else:
                processed_refs.append(clean_citation(str(ref).strip()))
        return "; ".join(processed_refs)
    elif isinstance(value, str):
        if value.strip().lower() in ("none", "nan"):
            return ""
        parts = [p.strip() for p in value.split(";")]
        processed_parts = []
        for part in parts:
            if part.lower() in ("none", "nan") or not part:
                continue
            if part.startswith("https://openalex.org/"):
                openalex_id = part.replace("https://openalex.org/", "").strip()
                citation = get_openalex_citation(openalex_id)
                if citation:
                    processed_parts.append(citation)
                else:
                    processed_parts.append(clean_citation(part))
            else:
                processed_parts.append(clean_citation(part))
        return "; ".join(processed_parts)
    return clean_citation(str(value).strip())


# =====================================================
# Extended Mapping for Additional Bibliometrix Fields
# =====================================================
extended_mapping = {
    "reference-count": ("NR", lambda v: v),
    "is-referenced-by-count": ("TC", lambda v: v),
    "ISSN": ("SN", lambda v: ", ".join(v) if isinstance(v, list) else v),
    "ISBN": ("BN", lambda v: ", ".join(v) if isinstance(v, list) else v),
    "funder": ("FU", lambda v: "; ".join([f.get("name", "") for f in v]) if isinstance(v, list) else v),
    "award": (
    "FX", lambda v: "; ".join([f.get("award", "") for f in v if f.get("award")]) if isinstance(v, list) else v),
    "paperId": ("ID", lambda v: v),
    "fieldsOfStudy": ("U1", lambda v: "; ".join(v) if isinstance(v, list) else v),
    "PMID": ("PM", lambda v: v),
    "license": ("OA", lambda v: "; ".join([lic.get("URL", "") for lic in v]) if isinstance(v, list) else v)
}

# Base mapping.
mapping = {
    "DOI": ("DI", lambda v: v),
    "title": ("TI", process_title),
    "container-title": ("SO", process_container_title),
    "author": ("AU", process_author),
    "issued": ("PY", process_issued),
    "volume": ("VL", lambda v: v),
    "issue": ("IS", lambda v: v),
    "page": (("BP", "EP"), process_page),
    "publisher": ("PU", lambda v: v),
    "abstract": ("AB", lambda v: v),
    "reference": ("CR", process_reference),
    "language": ("LA", lambda v: v),
    "affiliation": ("C1", lambda v: v),
    "keywords": ("DE", lambda v: v),
    "corresponding-author": ("RP", lambda v: v),
    "document-type": ("DT", lambda v: v)
}
mapping.update(extended_mapping)


# =====================================================
# Other API Query Functions
# =====================================================
def query_openalex_metadata(doi):
    url = f"https://api.openalex.org/works/doi:{doi}"
    try:
        response = robust_get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            meta = {}
            if "doi" in data:
                meta["DOI"] = data["doi"]
            if "display_name" in data:
                meta["title"] = data["display_name"]
            if "host_venue" in data and data["host_venue"]:
                meta["container-title"] = data["host_venue"].get("display_name", "")
            if "authorships" in data:
                authors = []
                for auth in data["authorships"]:
                    if "author" in auth and "display_name" in auth["author"]:
                        authors.append(auth["author"]["display_name"])
                if authors:
                    meta["author"] = "; ".join(authors)
            if "publication_year" in data:
                meta["issued"] = data["publication_year"]
            if "referenced_works" in data:
                meta["reference"] = data["referenced_works"]
            return True, meta
        return False, None
    except Exception as e:
        print(f"[OpenAlex] Error: {e}")
        return False, None


def query_pmc_metadata(doi):
    conv_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=BibliometrixMetadataEnhancer&email={EMAIL}&ids={doi}&format=json"
    try:
        conv_data = robust_json(conv_url, headers=HEADERS)
        if conv_data is None:
            print("[PMC] Skipping due to persistent JSON errors.")
            return False, None
        records = conv_data.get("records", [])
        if records and records[0].get("pmcid"):
            pmcid = records[0]["pmcid"]
        else:
            return False, None
    except Exception as e:
        print(f"[PMC IDConv] Error: {e}")
        return False, None

    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml"
    try:
        efetch_response = robust_get(efetch_url, headers=HEADERS)
        if efetch_response.status_code == 200:
            xml_data = efetch_response.text
            try:
                root = ET.fromstring(xml_data)
            except ET.ParseError as e:
                print(f"[PMC EFetch] XML parse error: {e}. Retrying in 30 seconds...")
                time.sleep(30)
                return query_pmc_metadata(doi)
            meta = {}
            title_elem = root.find(".//article-title")
            if title_elem is not None:
                meta["title"] = "".join(title_elem.itertext()).strip()
            journal_elem = root.find(".//journal-title")
            if journal_elem is not None:
                meta["container-title"] = "".join(journal_elem.itertext()).strip()
            lang = root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
            if lang:
                meta["language"] = lang
            pub_date = root.find(".//pub-date")
            if pub_date is not None:
                year_elem = pub_date.find("year")
                if year_elem is not None:
                    meta["issued"] = year_elem.text
            abstract_elem = root.find(".//abstract")
            if abstract_elem is not None:
                meta["abstract"] = "".join(abstract_elem.itertext()).strip()
            authors = []
            for contrib in root.findall(".//contrib[@contrib-type='author']"):
                name_elem = contrib.find("name")
                if name_elem is not None:
                    surname = name_elem.find("surname")
                    given = name_elem.find("given-names")
                    name_str = ""
                    if surname is not None:
                        name_str += surname.text
                    if given is not None:
                        name_str += ", " + given.text
                    if name_str:
                        authors.append(name_str)
            if authors:
                meta["author"] = "; ".join(authors)
            affiliations = []
            for aff in root.findall(".//aff"):
                aff_text = "".join(aff.itertext()).strip()
                if aff_text:
                    affiliations.append(aff_text)
            if affiliations:
                meta["affiliation"] = "; ".join(affiliations)
            keywords = []
            for kwd in root.findall(".//kwd"):
                kwd_text = "".join(kwd.itertext()).strip()
                if kwd_text:
                    keywords.append(kwd_text)
            if keywords:
                meta["keywords"] = "; ".join(keywords)
            corresp_elem = root.find(".//corresp")
            if corresp_elem is not None:
                meta["corresponding-author"] = "".join(corresp_elem.itertext()).strip()
            art_type = root.attrib.get("article-type")
            if art_type:
                meta["document-type"] = art_type
            refs = []
            for ref in root.findall(".//ref"):
                doi_elem = ref.find(".//pub-id[@pub-id-type='doi']")
                if doi_elem is not None and doi_elem.text:
                    refs.append(doi_elem.text.strip())
            if refs:
                meta["reference"] = "; ".join(refs)
            return True, meta
        else:
            return False, None
    except Exception as e:
        print(f"[PMC EFetch] Error: {e}")
        return False, None


def query_pubmed_metadata(query):
    pmid = None
    query_str = str(query).strip()
    if query_str.isdigit():
        pmid = query_str
    else:
        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query_str, "retmode": "json", "retmax": 1}
        data = robust_json(esearch_url, params=params, headers=HEADERS)
        if data is None:
            print("[PubMed] Skipping due to persistent JSON errors.")
            return False, None
        idlist = data.get("esearchresult", {}).get("idlist", [])
        if idlist:
            pmid = idlist[0]
    if pmid:
        ctxp_url = f"https://api.ncbi.nlm.nih.gov/lit/ctxp/v1/pubmed/?format=csl&id={pmid}"
        result = robust_json(ctxp_url, headers=HEADERS)
        if result is None:
            print("[PubMed] Skipping due to persistent JSON errors.")
            return False, None
        if isinstance(result, list):
            if len(result) == 0:
                print(f"[PubMed] Received an empty list for PMID {pmid}. Skipping.")
                return False, None
            result = result[0]
        if "DOI" in result and result["DOI"]:
            result["DOI"] = result["DOI"].strip()
        result["PMID"] = pmid
        return True, result
    return False, None


def query_nih_occ_metadata(doi):
    url = f"https://api.ncbi.nlm.nih.gov/oc/v1/citations/{doi}"
    try:
        response = robust_get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            citations = data.get("citations", [])
            if citations:
                return True, {"reference": process_reference(citations)}
        return False, None
    except Exception as e:
        print(f"[NIH-OCC] Error: {e}")
        return False, None


def query_crossref_metadata(doi_or_query, use_direct_lookup=True, spreadsheet_row=None):
    if use_direct_lookup and doi_or_query.startswith("10."):
        url = f"https://api.crossref.org/works/{doi_or_query}"
        response = robust_get(url, headers=HEADERS)
        if response.status_code == 200:
            return True, response.json().get("message", {})
        else:
            print(f"[Crossref] Direct lookup for {doi_or_query} returned {response.status_code}. Skipping.")
            return False, None
    return False, None


def query_semantic_scholar_metadata(doi):
    paper_id = f"DOI:{doi}"
    fields = "title,authors,year,venue,abstract,reference,fieldsOfStudy,paperId"
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields={fields}"
    try:
        response = robust_get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            meta = {}
            meta["DOI"] = doi
            if "title" in data:
                meta["title"] = data["title"]
            if "venue" in data:
                meta["container-title"] = data["venue"]
            if "authors" in data:
                authors = [author["name"] for author in data["authors"] if "name" in author]
                if authors:
                    meta["author"] = "; ".join(authors)
            if "year" in data:
                meta["issued"] = data["year"]
            if "abstract" in data:
                meta["abstract"] = data["abstract"]
            if "reference" in data:
                refs = []
                for ref in data["reference"]:
                    if "doi" in ref and ref["doi"]:
                        refs.append(ref["doi"])
                if refs:
                    meta["reference"] = "; ".join(refs)
            if "fieldsOfStudy" in data:
                meta["fieldsOfStudy"] = data["fieldsOfStudy"]
            if "paperId" in data:
                meta["paperId"] = data["paperId"]
            return True, meta
        else:
            return False, None
    except Exception as e:
        print(f"[Semantic Scholar] Error: {e}")
        return False, None


# =====================================================
# Mapping: API Response Keys -> Bibliometrix Field Tags
# =====================================================
mapping = {
    "DOI": ("DI", lambda v: v),
    "title": ("TI", process_title),
    "container-title": ("SO", process_container_title),
    "author": ("AU", process_author),
    "issued": ("PY", process_issued),
    "volume": ("VL", lambda v: v),
    "issue": ("IS", lambda v: v),
    "page": (("BP", "EP"), process_page),
    "publisher": ("PU", lambda v: v),
    "abstract": ("AB", lambda v: v),
    "reference": ("CR", process_reference),
    "language": ("LA", lambda v: v),
    "affiliation": ("C1", lambda v: v),
    "keywords": ("DE", lambda v: v),
    "corresponding-author": ("RP", lambda v: v),
    "document-type": ("DT", lambda v: v)
}
mapping.update({
    "reference-count": ("NR", lambda v: v),
    "is-referenced-by-count": ("TC", lambda v: v),
    "ISSN": ("SN", lambda v: ", ".join(v) if isinstance(v, list) else v),
    "ISBN": ("BN", lambda v: ", ".join(v) if isinstance(v, list) else v),
    "funder": ("FU", lambda v: "; ".join([f.get("name", "") for f in v]) if isinstance(v, list) else v),
    "award": (
    "FX", lambda v: "; ".join([f.get("award", "") for f in v if f.get("award")]) if isinstance(v, list) else v),
    "paperId": ("ID", lambda v: v),
    "fieldsOfStudy": ("U1", lambda v: "; ".join(v) if isinstance(v, list) else v),
    "PMID": ("PM", lambda v: v),
    "license": ("OA", lambda v: "; ".join([lic.get("URL", "") for lic in v]) if isinstance(v, list) else v)
})


# =====================================================
# Main Processing: Sequential Fallback with Streaming Logging, Checkpoints, and Excel Output using openpyxl
# =====================================================
def main():
    try:
        df = pd.read_excel(INPUT_FILE)
    except Exception as e:
        print(f"Error reading {INPUT_FILE}: {e}")
        return

    # Capture original columns.
    original_cols = set(df.columns)

    # Ensure all target columns exist.
    target_cols = set()
    for target, _ in mapping.values():
        if isinstance(target, tuple):
            target_cols.update(target)
        else:
            target_cols.add(target)
    target_cols.add("CR")
    for col in target_cols:
        if col not in df.columns:
            df[col] = ""

    # Force target columns to string type.
    for col in target_cols:
        df[col] = df[col].astype(str)

    empty_doi_counter = 0

    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write("Detailed Script Log\n")
        log_file.write("===================\n\n")
        print(f"Logging to {log_filename}")
        # Build API priority order.
        api_functions = []
        if SCOPUS_API_KEY.strip():
            api_functions.append(("Scopus", query_scopus_metadata))
        api_functions.extend([
            ("OpenAlex", query_openalex_metadata),
            ("PMC", query_pmc_metadata),
            ("PubMed", query_pubmed_metadata),
            ("NIH-OCC", query_nih_occ_metadata),
            ("Crossref", query_crossref_metadata),
            ("Semantic Scholar", query_semantic_scholar_metadata)
        ])

        for idx, row in df.iterrows():
            row_log = []  # Local log for this row.
            doi_raw = row.get("DI")
            doi = ""
            # Check if DI is missing or empty.
            if pd.isna(doi_raw) or str(doi_raw).strip() == "":
                found_doi = None
                # First check AID column.
                if "AID" in df.columns and row.get("AID"):
                    aid_str = str(row.get("AID")).strip()
                    row_log.append(f"Row {idx}: DI empty. AID field found: {aid_str}")
                    for part in [p.strip() for p in aid_str.split(";")]:
                        if "[DOI]" in part:
                            candidate = part.replace("[DOI]", "").strip()
                            if candidate.startswith("10."):
                                found_doi = candidate
                                row_log.append(f"Row {idx}: Using DOI from AID: {found_doi}")
                                break
                        elif part.startswith("10."):
                            found_doi = part
                            row_log.append(f"Row {idx}: Using DOI from AID: {found_doi}")
                            break
                # If still not found, try title-based search.
                if not found_doi:
                    title_val = row.get("TI")
                    abstract_val = row.get("AB")
                    if title_val and str(title_val).strip() != "":
                        row_log.append(
                            f"Row {idx}: DI empty and no valid DOI in AID. Querying Scopus with title: {title_val}")
                        success, metadata = query_scopus_by_title(title_val, abstract=abstract_val)
                        if success and metadata and "DOI" in metadata:
                            found_doi = metadata["DOI"]
                            row_log.append(f"Row {idx}: Scopus title/abstract query returned DOI: {found_doi}")
                        else:
                            row_log.append(f"Row {idx}: Scopus title/abstract query failed.")
                    else:
                        row_log.append(f"Row {idx}: DI empty and no title available. Skipping row.")
                        empty_doi_counter += 1
                        log_file.write("\n".join(row_log) + "\n" + "-" * 80 + "\n")
                        log_file.flush()
                        # Save checkpoint every 100 rows if needed.
                        if (idx + 1) % 100 == 0:
                            save_to_excel(df, OUTPUT_FILE)
                        continue
                doi = found_doi if found_doi else ""
                if not doi:
                    row_log.append(f"Row {idx}: No valid DOI found after AID/title search. Skipping row.")
                    empty_doi_counter += 1
                    log_file.write("\n".join(row_log) + "\n" + "-" * 80 + "\n")
                    log_file.flush()
                    if (idx + 1) % 100 == 0:
                        save_to_excel(df, OUTPUT_FILE)
                    continue
                # Overwrite DI with the found DOI.
                df.at[idx, "DI"] = doi
                row_log.append(f"Row {idx}: DI updated with found DOI: {doi}")
            else:
                doi = str(doi_raw).strip()
                row_log.append(f"Row {idx}: Found DI = {doi}")
                # If DI exists but is not a valid DOI, try to update it.
                if not doi.startswith("10."):
                    found_doi = None
                    if "AID" in df.columns and row.get("AID"):
                        aid_str = str(row.get("AID")).strip()
                        row_log.append(f"Row {idx}: DI is not a valid DOI. AID field found: {aid_str}")
                        for part in [p.strip() for p in aid_str.split(";")]:
                            if "[DOI]" in part:
                                candidate = part.replace("[DOI]", "").strip()
                                if candidate.startswith("10."):
                                    found_doi = candidate
                                    row_log.append(f"Row {idx}: Using DOI from AID: {found_doi}")
                                    break
                            elif part.startswith("10."):
                                found_doi = part
                                row_log.append(f"Row {idx}: Using DOI from AID: {found_doi}")
                                break
                    if not found_doi:
                        title_val = row.get("TI")
                        abstract_val = row.get("AB")
                        if title_val and str(title_val).strip() != "":
                            row_log.append(
                                f"Row {idx}: DI is not valid and no DOI in AID. Querying Scopus with title: {title_val}")
                            success, metadata = query_scopus_by_title(title_val, abstract=abstract_val)
                            if success and metadata and "DOI" in metadata:
                                found_doi = metadata["DOI"]
                                row_log.append(f"Row {idx}: Scopus title/abstract query returned DOI: {found_doi}")
                            else:
                                row_log.append(f"Row {idx}: Scopus title/abstract query failed.")
                    if found_doi:
                        doi = found_doi
                        df.at[idx, "DI"] = doi  # Overwrite DI with the valid DOI.
                        row_log.append(f"Row {idx}: DI updated with found DOI: {doi}")
                    else:
                        row_log.append(f"Row {idx}: No valid DOI found; using original DI value: {doi}")

            # Log title if available.
            title_val = row.get("TI")
            if title_val:
                row_log.append(f"Row {idx}: Title from TI = {title_val}")

            # Query each API in priority order using the (possibly updated) doi.
            for label, api_fn in api_functions:
                if label == "Scopus":
                    row_log.append(f"Row {idx}: Querying {label} API with DOI '{doi}' and title '{title_val}'")
                    success, metadata = api_fn(doi, title=title_val)
                else:
                    row_log.append(f"Row {idx}: Querying {label} API with DOI '{doi}'")
                    success, metadata = api_fn(doi)
                if success and metadata:
                    row_log.append(f"Row {idx}: Retrieved metadata from {label}.")
                    # For each mapped field, update only if the corresponding column originally existed.
                    for key, (target_field, func) in mapping.items():
                        if isinstance(target_field, tuple):
                            if not all(tf in original_cols for tf in target_field):
                                continue
                        else:
                            if target_field not in original_cols:
                                continue

                        # Check current value.
                        if isinstance(target_field, tuple):
                            current_bp = str(df.at[idx, "BP"]).strip().lower()
                            current_ep = str(df.at[idx, "EP"]).strip().lower()
                            if current_bp and current_bp not in ("none", "nan") and current_ep and current_ep not in (
                            "none", "nan"):
                                continue
                        else:
                            current_val = str(df.at[idx, target_field]).strip().lower()
                            if current_val and current_val not in ("none", "nan"):
                                continue

                        if key in metadata:
                            new_value = func(metadata[key])
                            if isinstance(new_value, tuple):
                                bp, ep = new_value
                                bp_str = str(bp).strip()
                                ep_str = str(ep).strip()
                                if bp_str.lower() in ("none", "nan", "") and ep_str.lower() in ("none", "nan", ""):
                                    continue
                                old_bp = str(df.at[idx, "BP"]).strip()
                                old_ep = str(df.at[idx, "EP"]).strip()
                                if (not old_bp or old_bp.lower() in ("none", "nan")) and bp_str not in (
                                "none", "nan", ""):
                                    df.at[idx, "BP"] = bp_str
                                    row_log.append(f"Row {idx}: BP updated from '{old_bp}' to '{bp_str}' via {label}.")
                                if (not old_ep or old_ep.lower() in ("none", "nan")) and ep_str not in (
                                "none", "nan", ""):
                                    df.at[idx, "EP"] = ep_str
                                    row_log.append(f"Row {idx}: EP updated from '{old_ep}' to '{ep_str}' via {label}.")
                            else:
                                new_value_str = str(new_value).strip()
                                if new_value_str.lower() in ("none", "nan", ""):
                                    continue
                                old_val = str(df.at[idx, target_field]).strip()
                                df.at[idx, target_field] = new_value_str
                                row_log.append(
                                    f"Row {idx}: {target_field} updated from '{old_val}' to '{new_value_str}' via {label}.")
                else:
                    row_log.append(f"Row {idx}: {label} API failed or returned no data.")

            separator = "-" * 80
            log_message = "\n".join(row_log) + "\n" + separator + "\n"
            print(log_message)
            log_file.write(log_message)
            log_file.flush()
            # Save checkpoint every 100 rows.
            if (idx + 1) % 100 == 0:
                save_to_excel(df, OUTPUT_FILE)

        log_file.write(f"\nTotal records processed: {len(df)}\n")
        log_file.write(f"Total rows with no valid DOI after AID/title search: {empty_doi_counter}\n")
        print(f"Total records processed: {len(df)}")
        print(f"Total rows with no valid DOI: {empty_doi_counter}")

    # Final save using openpyxl's write-only mode.
    try:
        save_to_excel(df, OUTPUT_FILE)
        print(f"Updated Excel file saved as {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving final output to {OUTPUT_FILE}: {e}")


if __name__ == "__main__":
    main()
