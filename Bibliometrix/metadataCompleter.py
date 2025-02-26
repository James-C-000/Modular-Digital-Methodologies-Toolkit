r"""
Enrich exported bibliometric records by sequentially querying multiple APIs for metadata.
For each record (row) in the input Excel file, the script queries the APIs with priority order:
    1. NIH Open Citation Collection (NIH-OCC)
    2. PubMed
    3. PubMed Central (PMC)
    4. OpenAlex
    5. Crossref
    6. Semantic Scholar
For each record, any cell that is empty or contains "none" (case insensitive) is updated with data
returned by the API. A changelog is produced detailing every cell update, along with a summary.
API responses are mapped to Bibliometrix field tags.
"""

import time
import pandas as pd
import requests
import json
import xml.etree.ElementTree as ET
import re

# =====================================================
# Global Configuration
# =====================================================
EMAIL = "your_email_here@example.com"  # Replace with your actual email address
INPUT_FILE = "./records/mergedDataset.xlsx"
OUTPUT_FILE = "./records/mergedDatasetEnhanced.xlsx"
CHANGELOG_FILE = "changelog.txt"
SEMANTIC_SCHOLAR_API_KEY = ""  # Supply your Semantic Scholar API key if available

HEADERS = {
    "User-Agent": f"BibliometrixMetadataEnhancer/1.0 (mailto:{EMAIL})",
    "From": EMAIL,
    "Accept": "application/json"
}
if SEMANTIC_SCHOLAR_API_KEY:
    HEADERS["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

# Global cache for OpenAlex citation lookups
openalex_cache = {}

# Global changelog structures
changelog_entries = []       # List of change log entries
column_edit_counts = {}      # Dictionary: column -> count of edits
rows_changed = set()         # Set of row indices that were changed

# =====================================================
# Robust Network Functions
# =====================================================
def robust_get(url, **kwargs):
    """
    A robust wrapper around requests.get that catches various transient errors
    and retries indefinitely until a valid response is received.
    It handles:
      - ConnectionError
      - Timeout (including ConnectTimeout and ReadTimeout)
      - ChunkedEncodingError
      - RequestException (covers any other requests-related errors)
    """
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

def robust_json(url, **kwargs):
    """
    A helper that retrieves a URL using robust_get() and attempts to decode its JSON.
    If a JSONDecodeError occurs, it waits 30 seconds and retries.
    """
    while True:
        response = robust_get(url, **kwargs)
        try:
            return response.json()
        except json.decoder.JSONDecodeError as e:
            print(f"JSON decode error for {url}: {e}. Retrying in 30 seconds...")
            time.sleep(30)

# =====================================================
# Helper Functions to Process Metadata Fields
# =====================================================

def clean_citation(citation):
    r"""
    Remove HTML tags and any leading numbering (e.g., "1)" or "1.") from a citation string.
    """
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

def get_openalex_citation(openalex_id):
    r"""
    Given an OpenAlex work ID (e.g., "W136575539"), query OpenAlex for its metadata
    and format a citation as: AUTHORS, TITLE, JOURNAL, VOLUME, (YEAR)
    Uses caching to avoid redundant API calls
    """
    if openalex_id in openalex_cache:
        return openalex_cache[openalex_id]
    url = f"https://api.openalex.org/works/{openalex_id}"
    try:
        resp = robust_get(url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            authors = []
            if "authorships" in data:
                for auth in data["authorships"]:
                    if "author" in auth and "display_name" in auth["author"]:
                        authors.append(auth["author"]["display_name"].upper())
            authors_str = ", ".join(authors)
            title = data.get("title", "").strip()
            journal = ""
            if "host_venue" in data and data["host_venue"]:
                journal = data["host_venue"].get("display_name", "").strip().upper()
            volume = data.get("volume", "")
            year = data.get("publication_year", "")
            parts = []
            if authors_str:
                parts.append(authors_str)
            if title:
                parts.append(title)
            if journal:
                parts.append(journal)
            if volume:
                parts.append(volume)
            if year:
                parts.append(f"({year})")
            citation = ", ".join(parts)
            citation = clean_citation(citation)
            openalex_cache[openalex_id] = citation
            return citation
        else:
            return None
    except Exception as e:
        print(f"[OpenAlex Lookup] Error: {e}")
        return None

def process_reference(value):
    r"""
    Process the reference field into a formatted string.
    - If value is a list:
         - For dictionaries (e.g., from Crossref), extract and clean the 'unstructured' field if available.
         - For strings:
              - If it matches an OpenAlex ID pattern (e.g., "W123456") or starts with "https://openalex.org/",
                convert it into a full citation using get_openalex_citation().
              - Otherwise, clean the string.
         - Join all processed references with "; " as delimiter.
    - If value is a string containing semicolons, split and process each part.
    """
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
                if rstr.lower() == "none":
                    continue
                if re.match(r'^W\d+$', rstr):
                    citation = get_openalex_citation(rstr)
                    if citation:
                        processed_refs.append(citation)
                elif rstr.startswith("https://openalex.org/"):
                    openalex_id = rstr.replace("https://openalex.org/", "").strip()
                    citation = get_openalex_citation(openalex_id)
                    if citation:
                        processed_refs.append(citation)
                else:
                    processed_refs.append(clean_citation(rstr))
            else:
                processed_refs.append(clean_citation(str(ref).strip()))
        return "; ".join(processed_refs)
    elif isinstance(value, str):
        if value.strip().lower() == "none":
            return ""
        parts = [p.strip() for p in value.split(";")]
        processed_parts = []
        for part in parts:
            if part.lower() == "none" or not part:
                continue
            if re.match(r'^W\d+$', part):
                citation = get_openalex_citation(part)
                if citation:
                    processed_parts.append(citation)
            elif part.startswith("https://openalex.org/"):
                openalex_id = part.replace("https://openalex.org/", "").strip()
                citation = get_openalex_citation(openalex_id)
                if citation:
                    processed_parts.append(citation)
            else:
                processed_parts.append(clean_citation(part))
        return "; ".join(processed_parts)
    return clean_citation(str(value).strip())

# =====================================================
# API Query Functions
# =====================================================

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

def query_pubmed_metadata(query):
    pmid = None
    query_str = str(query).strip()
    if query_str.isdigit():
        pmid = query_str
    else:
        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query_str, "retmode": "json", "retmax": 1}
        r = robust_get(esearch_url, params=params, headers=HEADERS)
        if r.status_code == 200:
            idlist = r.json().get("esearchresult", {}).get("idlist", [])
            if idlist:
                pmid = idlist[0]
        else:
            return False, None
    if pmid:
        ctxp_url = f"https://api.ncbi.nlm.nih.gov/lit/ctxp/v1/pubmed/?format=csl&id={pmid}"
        r = robust_get(ctxp_url, headers=HEADERS)
        if r.status_code == 200:
            try:
                result = r.json()
                if "DOI" in result and result["DOI"]:
                    result["DOI"] = result["DOI"].strip()
                return True, result
            except json.decoder.JSONDecodeError as e:
                print(f"[PubMed] JSON decode error: {e}. Retrying in 30 seconds...")
                time.sleep(30)
                return query_pubmed_metadata(query)
            except Exception as e:
                print(f"[PubMed] Error parsing response: {e}")
                return False, None
        else:
            return False, None
    return False, None

def query_pmc_metadata(doi):
    conv_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=BibliometrixMetadataEnhancer&email={EMAIL}&ids={doi}&format=json"
    try:
        conv_response = robust_get(conv_url, headers=HEADERS)
        if conv_response.status_code == 200:
            conv_data = conv_response.json()
            records = conv_data.get("records", [])
            if records and records[0].get("pmcid"):
                pmcid = records[0]["pmcid"]
            else:
                return False, None
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
                meta["reference"] = data["referenced_works"]  # leave as list
            return True, meta
        return False, None
    except Exception as e:
        print(f"[OpenAlex] Error: {e}")
        return False, None

def query_crossref_metadata(doi_or_query, use_direct_lookup=True, spreadsheet_row=None):
    # Only direct lookup (removed query for providing false positives)
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
    fields = "title,authors,year,venue,abstract,reference"
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
            return True, meta
        else:
            return False, None
    except Exception as e:
        print(f"[Semantic Scholar] Error: {e}")
        return False, None

# =====================================================
# Mapping: API Response Keys -> Bibliometrix Columns
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

# =====================================================
# Main Processing: Sequential Fallback Approach with Changelog
# =====================================================
def main():
    try:
        df = pd.read_excel(INPUT_FILE)
    except Exception as e:
        print(f"Error reading {INPUT_FILE}: {e}")
        return

    # Ensure all target columns exist
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

    empty_doi_counter = 0

    # Initialize changelog structures
    global changelog_entries, column_edit_counts, rows_changed
    changelog_entries = []
    column_edit_counts = {}
    rows_changed = set()

    # Define API functions in strict priority order:
    # 1. NIH-OCC, 2. PubMed, 3. PMC, 4. OpenAlex, 5. Crossref, 6. Semantic Scholar
    api_functions = [
        ("NIH-OCC", query_nih_occ_metadata),
        ("PubMed", query_pubmed_metadata),
        ("PMC", query_pmc_metadata),
        ("OpenAlex", query_openalex_metadata),
        ("Crossref", query_crossref_metadata),
        ("Semantic Scholar", query_semantic_scholar_metadata)
    ]

    # Process each record
    for idx, row in df.iterrows():
        doi_raw = row.get("DI")
        if not doi_raw or str(doi_raw).strip() == "":
            print(f"Row {idx}: Empty DOI in 'DI'. Skipping.")
            empty_doi_counter += 1
            continue

        doi = str(doi_raw).strip()

        for label, api_fn in api_functions:
            success, metadata = api_fn(doi)
            if success and metadata:
                print(f"Row {idx}: Retrieved metadata from {label}.")
                for key, (target_field, func) in mapping.items():
                    # Check if field is already populated (treat "none" as empty)
                    if isinstance(target_field, tuple):
                        current_bp = str(row.get("BP", "")).strip().lower()
                        current_ep = str(row.get("EP", "")).strip().lower()
                        if current_bp and current_bp != "none" and current_ep and current_ep != "none":
                            continue
                    else:
                        current_val = str(row.get(target_field, "")).strip().lower()
                        if current_val and current_val != "none":
                            continue

                    if key in metadata:
                        new_value = func(metadata[key])
                        if isinstance(new_value, str) and (new_value.strip().lower() == "none" or new_value.strip() == ""):
                            continue
                        # Log the change
                        if isinstance(target_field, tuple):
                            old_bp = str(row.get("BP", ""))
                            old_ep = str(row.get("EP", ""))
                            bp, ep = new_value
                            if not old_bp or old_bp.lower() == "none":
                                df.at[idx, "BP"] = bp
                                changelog_entries.append(f"Row {idx} - BP updated from '{old_bp}' to '{bp}' via {label}.\n")
                                changelog_entries.append("----------------------------------")
                                column_edit_counts["BP"] = column_edit_counts.get("BP", 0) + 1
                            if not old_ep or old_ep.lower() == "none":
                                df.at[idx, "EP"] = ep
                                changelog_entries.append(f"Row {idx} - EP updated from '{old_ep}' to '{ep}' via {label}.\n")
                                changelog_entries.append("----------------------------------")
                                column_edit_counts["EP"] = column_edit_counts.get("EP", 0) + 1
                        else:
                            old_val = str(row.get(target_field, ""))
                            df.at[idx, target_field] = new_value
                            changelog_entries.append(f"Row {idx} - {target_field} updated from '{old_val}' to '{new_value}' via {label}.")
                            changelog_entries.append("----------------------------------")
                            column_edit_counts[target_field] = column_edit_counts.get(target_field, 0) + 1
                        rows_changed.add(idx)
                row = df.loc[idx]
        # End processing for this record

    total_changed_records = len(rows_changed)
    print(f"Total records changed: {total_changed_records}")
    print(f"Total rows with empty DOI: {empty_doi_counter}")
    try:
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"Updated Excel file saved as {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving {OUTPUT_FILE}: {e}")

    # Write changelog to file
    try:
        with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
            f.write("Changelog of Spreadsheet Updates\n")
            f.write("----------------------------------\n\n")
            f.write(f"Total records changed: {total_changed_records}\n")
            for col, count in column_edit_counts.items():
                f.write(f"Column {col} updated {count} times.\n")
            f.write("\nDetailed Changes:\n")
            for entry in changelog_entries:
                f.write(entry + "\n")
        print(f"Changelog saved as {CHANGELOG_FILE}")
    except Exception as e:
        print(f"Error writing changelog: {e}")

if __name__ == "__main__":
    main()
