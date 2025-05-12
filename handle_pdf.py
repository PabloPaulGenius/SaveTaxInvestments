import tempfile
import requests

import pdfplumber

import logging
def download_pdf(url):
    """
    Downloads a PDF from the given URL to a temporary file and returns the file path.
    Args:
        url (str): The URL of the PDF to download.
    Returns:
        str or None: The file path to the downloaded PDF, or None if download fails.
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            return tmp_file.name
    except Exception as e:
        logging.error(f"Failed to download PDF from {url}: {e}")
        return None

def extract_dividendenrendite_from_pdf(pdf_path):
    """
    Extracts the percentage value next to 'Dividendenrendite', 'Dividende', or 'Rendite' (case-insensitive, in that order of priority) from the PDF using pdfplumber.
    Handles cases where the value is on the same line or the next line. Only valid percentage values (e.g., 2,02%) are returned.
    Args:
        pdf_path (str): The file path to the PDF file.
    Returns:
        str: The extracted value (e.g., '2,02%'), or 'no DivRendite found' if not found.
    """
    import re
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        lines = text.splitlines()
        # Priority order
        keyword_priority = [r"Dividendenrendite", r"Dividende", r"Rendite"]
        percent_pattern = r"([\d]{1,3}[\.,][\d]{1,3}\s*%|[\d]{1,3}\s*%)"
        for kw in keyword_priority:
            for i, line in enumerate(lines):
                if re.search(kw, line, re.IGNORECASE):
                    matches = re.findall(percent_pattern, line)
                    matches = [m.strip() for m in matches if re.search(r"\d", m)]
                    if matches:
                        return matches[0]
                    if i + 1 < len(lines):
                        matches_next = re.findall(percent_pattern, lines[i+1])
                        matches_next = [m.strip() for m in matches_next if re.search(r"\d", m)]
                        if matches_next:
                            return matches_next[0]
            # Fallback: search the whole text for keyword followed by percentage
            match = re.search(kw + r"[\s:]*([\d]{1,3}[\.,][\d]{1,3}\s*%|[\d]{1,3}\s*%)", text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if re.search(r"\d", val):
                    return val
        return 'no DivRendite found'
    except Exception as e:
        logging.error(f"Failed to extract Dividendenrendite/Dividende/Rendite from PDF: {e}")
        return 'no DivRendite found'