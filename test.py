import requests
import csv
import argparse
import sys
import re
import xml.etree.ElementTree as ET
from typing import List, Dict

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DETAILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
FULL_DETAILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

COMPANY_KEYWORDS = ["Inc", "Ltd", "LLC", "Pharma", "Biotech", "Therapeutics", "Laboratories", "Corp", "GmbH"]
COMPANY_EMAIL_DOMAINS = ["@pfizer.com", "@gsk.com", "@novartis.com", "@merck.com", "@roche.com"]

def fetch_pubmed_papers(query: str, max_results: int = 10) -> List[Dict]:
    """Fetch papers from PubMed based on a query."""
    response = requests.get(BASE_URL, params={
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    })
    response.raise_for_status()
    paper_ids = response.json().get("esearchresult", {}).get("idlist", [])
    return get_paper_details(paper_ids) if paper_ids else []

def get_paper_details(paper_ids: List[str]) -> List[Dict]:
    """Fetch detailed information about papers."""
    if not paper_ids:
        return []
    response = requests.get(DETAILS_URL, params={
        "db": "pubmed",
        "id": ",".join(paper_ids),
        "retmode": "json"
    })
    response.raise_for_status()
    return parse_paper_details(response.json().get("result", {}), paper_ids)

def parse_paper_details(results: Dict, paper_ids: List[str]) -> List[Dict]:
    """Extract relevant details from PubMed response."""
    papers = []
    for paper_id in paper_ids:
        details = results.get(paper_id, {})
        authors = details.get("authors", [])
        non_academic_authors, company_affiliations = extract_non_academic_authors(paper_id)
        corresponding_author_email = fetch_corresponding_email(paper_id)
        
        papers.append({
            "PubmedID": paper_id,
            "Title": details.get("title", "N/A"),
            "Publication Date": details.get("pubdate", "N/A"),
            "Non-academic Author(s)": ", ".join(non_academic_authors) if non_academic_authors else "N/A",
            "Company Affiliation(s)": ", ".join(company_affiliations) if company_affiliations else "N/A",
            "Corresponding Author Email": corresponding_author_email
        })
    return papers

def extract_non_academic_authors(paper_id: str) -> (List[str], List[str]):
    """Extract author affiliations from full-text metadata."""
    response = requests.get(FULL_DETAILS_URL, params={
        "db": "pubmed",
        "id": paper_id,
        "rettype": "xml",
        "retmode": "text"
    })
    response.raise_for_status()
    root = ET.fromstring(response.text)
    
    non_academic_authors = []
    company_affiliations = []
    
    for author in root.findall(".//Author"):
        name = author.find("LastName").text if author.find("LastName") is not None else "Unknown"
        affiliation = author.find("AffiliationInfo/Affiliation")
        
        if affiliation is not None:
            affiliation_text = affiliation.text
            if any(keyword in affiliation_text for keyword in COMPANY_KEYWORDS):
                non_academic_authors.append(name)
                company_affiliations.append(affiliation_text)
    
    return non_academic_authors, company_affiliations

def fetch_corresponding_email(paper_id: str) -> str:
    """Fetch the corresponding author's email from full article XML."""
    response = requests.get(FULL_DETAILS_URL, params={
        "db": "pubmed",
        "id": paper_id,
        "rettype": "xml",
        "retmode": "text"
    })
    response.raise_for_status()
    root = ET.fromstring(response.text)
    
    for email in root.findall(".//Author/ContactInfo/Email"):
        return email.text
    
    return "N/A"

def save_to_csv(papers: List[Dict], filename: str):
    """Save extracted paper details to a CSV file with a fixed column order."""
    if not papers:
        print("No papers found to save.")
        return
    column_order = ["PubmedID", "Title", "Publication Date", "Non-academic Author(s)", "Company Affiliation(s)", "Corresponding Author Email"]
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=column_order)
        writer.writeheader()
        writer.writerows(papers)

def main():
    parser = argparse.ArgumentParser(description="Fetch research papers from PubMed based on a query.")
    parser.add_argument("query", type=str, help="Search query for PubMed")
    parser.add_argument("-f", "--file", type=str, help="Output CSV file name")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    if args.debug:
        print(f"Fetching papers for query: {args.query}")
    
    papers = fetch_pubmed_papers(args.query)
    if args.file:
        save_to_csv(papers, args.file)
        print(f"Results saved to {args.file}")
    else:
        print(papers)

if __name__ == "__main__":
    main()
