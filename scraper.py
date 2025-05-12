import time
# import requests # No longer needed
from bs4 import BeautifulSoup
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from write_to_db import *
import os
import tempfile
import requests
import PyPDF2
import pdfplumber


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



URL = "https://www.justetf.com/de/etf-list-overview.html#aktien_asien-pazifik"
BASE_URL = "https://www.justetf.com"
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 20
COOKIE_BUTTON_TEXT = "Auswahl erlauben"
# SECTION_HEADER_TEXT = "Aktien Asien-Pazifik" # No longer primary targeting mechanism

def setup_driver():
    """
    Sets up the Selenium WebDriver with Chrome and returns the driver instance.
    Returns:
        webdriver.Chrome: The configured Selenium WebDriver instance, or None if setup fails.
    """
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Keep visible for now
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    #options.add_argument("--start-maximized") # Start maximized to help with element visibility

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        logging.info("WebDriver setup complete.")
        return driver
    except WebDriverException as e:
        logging.error(f"WebDriver setup failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during WebDriver setup: {e}")
        return None

# Removed scroll_until_element_found function

def find_first_two_etf_links(driver):
    """
    Parses the current page to find the first two ETF profile links where the 6th column contains 'Ausschütt'.
    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
    Returns:
        list: List of up to two ETF profile URLs (strings).
    """
    logging.info("Parsing page HTML to find the first two matching ETF links...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    target_table_selector = "table.table.table-striped.dataTable.no-footer"
    data_tables = soup.select(target_table_selector)
    logging.info(f"Found {len(data_tables)} table(s) matching selector '{target_table_selector}'.")

    if not data_tables:
        logging.warning(f"No tables found matching '{target_table_selector}'.")
        return []

    found_links = []
    for table_index, table in enumerate(data_tables):
        logging.info(f"Processing Table {table_index + 1}...")
        table_body = table.find('tbody')
        if not table_body:
            logging.warning(f"  Table {table_index + 1} has no tbody. Skipping.")
            continue

        rows = table_body.find_all('tr')
        logging.info(f"  Found {len(rows)} rows in Table {table_index + 1} tbody.")

        for row_index, row in enumerate(rows):
            columns = row.find_all('td', recursive=False)
            if len(columns) >= 6:
                column_6_text = columns[5].get_text(strip=True)
                if column_6_text.startswith("Ausschütt"):
                    first_column = columns[0]
                    link_tag = first_column.find('a')
                    if link_tag and link_tag.find('i') is None:
                        anchor_text = link_tag.get_text(strip=True)
                        anchor_href = link_tag.get('href')
                        if anchor_href:
                            if anchor_href.startswith('/'):
                                anchor_href = BASE_URL + anchor_href
                            logging.info(f"  FOUND MATCH: Table {table_index+1}, Row {row_index+1}: Link='{anchor_text}', Col6='{column_6_text}', Href='{anchor_href}'")
                            found_links.append(anchor_href)
                            if len(found_links) == 2:
                                return found_links
    if not found_links:
        logging.warning("No ETF links matching all criteria found on the page.")
    return found_links

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

def parse_first_three_tables(driver):
    """
    Parses the first three tables on the page, logs the table name, number of rows, and number of 'Ausschütt' matches.
    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
    Returns:
        list of dict: Each dict contains ETF data for a row (columns 1-8, keys: 'name', 'ter', 'ytd', 'fondsgröße', 'auflagedatum', 'ausschüttung', 'replikation', 'isin', 'row', 'profile_url').
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    target_table_selector = "table.table.table-striped.dataTable.no-footer"
    data_tables = soup.select(target_table_selector)
    etf_rows = []
    for table_index, table in enumerate(data_tables[:3]):  # Only first 3 tables
        # Find the closest previous <h3> tag for the table name
        table_name = None
        for prev in table.find_all_previous():
            if prev.name == 'h3':
                table_name = prev.get_text(strip=True)
                break
        if not table_name:
            table_name = f"Table {table_index+1}"  # fallback
        table_body = table.find('tbody')
        if not table_body:
            logging.info(f"{table_name}: No tbody found. Skipping.")
            continue
        rows = table_body.find_all('tr')
        total_rows = len(rows)
        match_count = 0
        for row in rows:
            columns = row.find_all('td', recursive=False)
            if len(columns) >= 8:
                col6 = columns[5].get_text(strip=True)
                if col6.startswith("Ausschütt"):
                    # Extract ETF name from first <a> in first <td> (without <i> tag)
                    first_td = columns[0]
                    link_tag = first_td.find('a')
                    if link_tag and not link_tag.find('i'):
                        etf_name = link_tag.get_text(strip=True)
                        href = link_tag.get('href')
                        profile_url = BASE_URL + href if href and href.startswith('/') else href
                    else:
                        continue  # skip if no valid anchor
                    match_count += 1
                    etf_data = {
                        'name': etf_name,
                        'ter': columns[1].get_text(strip=True),
                        'ytd': columns[2].get_text(strip=True),
                        'fondsgröße': columns[3].get_text(strip=True),
                        'auflagedatum': columns[4].get_text(strip=True),
                        'ausschüttung': columns[5].get_text(strip=True),
                        'replikation': columns[6].get_text(strip=True),
                        'isin': columns[7].get_text(strip=True),
                        'row': [c.get_text(strip=True) for c in columns[:8]],
                        'profile_url': profile_url,
                        'table_name': table_name
                    }
                    etf_rows.append(etf_data)
        logging.info(f"{table_name}: {total_rows} rows, {match_count} Ausschütt matches.")
    return etf_rows

def save_etf_data_to_txt(etf_data_list, filename):
    """
    Saves a list of ETF data dicts to a .txt file, one row per line, tab-separated. Includes Dividendenrendite if present.
    Args:
        etf_data_list (list of dict): List of ETF data dicts.
        filename (str): Output filename.
    Returns:
        None
    """
    headers = ['Name', 'TER', 'YTD', 'Fondsgröße', 'Auflagedatum', 'Ausschüttung', 'Replikation', 'ISIN', 'Dividendenrendite']
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\t'.join(headers) + '\n')
        for etf in etf_data_list:
            row = [etf.get('name', ''), etf.get('ter', ''), etf.get('ytd', ''), etf.get('fondsgröße', ''),
                   etf.get('auflagedatum', ''), etf.get('ausschüttung', ''), etf.get('replikation', ''), etf.get('isin', ''),
                   etf.get('dividendenrendite', '')]
            f.write('\t'.join(row) + '\n')

def scrape_etf_links():
    """
    Main scraping function. Parses the first three tables, collects all Ausschütt ETF rows, downloads their factsheets, extracts Dividendenrendite, and saves all data to a .txt file.
    Returns:
        None
    """
    driver = setup_driver()
    if not driver:
        return "WebDriver setup failed."

    try:
        logging.info(f"Fetching data from {URL}...")
        driver.get(URL)

        # Handle Cookie Consent Pop-up
        try:
            cookie_button_xpath = f"//button[normalize-space()='{COOKIE_BUTTON_TEXT}']"
            logging.info(f"Waiting for cookie consent button: '{COOKIE_BUTTON_TEXT}'...")
            cookie_button = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))
            )
            logging.info("Cookie button found. Clicking...")
            cookie_button.click()
            logging.info("Clicked cookie button. Pausing for page to settle...")
            time.sleep(3)
        except TimeoutException:
            logging.warning(f"Cookie button '{COOKIE_BUTTON_TEXT}' not found. Proceeding...")
        except Exception as e:
            logging.error(f"Error clicking cookie button: {e}. Proceeding...")

        logging.info("Waiting for page content to stabilize after navigation/cookie handling...")
        time.sleep(5)

        # Step 1: Parse the first three tables and collect Ausschütt ETF rows
        etf_rows = parse_first_three_tables(driver)
        if not etf_rows:
            print("No Ausschütt ETFs found in the first three tables.")
            return

        # Step 2: For each ETF, extract Dividendenrendite from factsheet if possible
        for idx, etf in enumerate(etf_rows, 1):
            profile_url = etf.get('profile_url')
            if not profile_url:
                etf['dividendenrendite'] = ''
                continue
            logging.info(f"\nProcessing ETF {idx}: {etf['name']} ({profile_url})")
            driver.get(profile_url)
            # Wait for a known element on the profile page to ensure it's loaded
            logging.info("Waiting for ETF profile page to load (e.g., for an h1 tag)...")
            try:
                WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                logging.info("ETF profile page loaded (h1 found).")
            except TimeoutException:
                logging.error("Timed out waiting for ETF profile page content (h1). Proceeding to find factsheet anyway.")

            # Step 2: Find the "Factsheet (DE)" link on the profile page
            factsheet_link_xpath = "//a[contains(@class, 'download-link') and @title='Factsheet (DE)' and contains(normalize-space(), 'Factsheet (DE)')]"
            logging.info(f"Looking for Factsheet link with XPath: {factsheet_link_xpath}")
            try:
                factsheet_anchor = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, factsheet_link_xpath))
                )
                factsheet_href = factsheet_anchor.get_attribute('href')
                if factsheet_href:
                    if factsheet_href.startswith('/'):
                        factsheet_href_abs = BASE_URL + factsheet_href
                    else:
                        factsheet_href_abs = factsheet_href
                    logging.info(f"Found Factsheet link: {factsheet_href_abs}. Downloading PDF...")
                    pdf_path = download_pdf(factsheet_href_abs)
                    if pdf_path:
                        div_rendite = extract_dividendenrendite_from_pdf(pdf_path)
                        if div_rendite:
                            etf['dividendenrendite'] = div_rendite
                            logging.info(f"ETF {idx}: Dividendenrendite found: {div_rendite}")
                        else:
                            etf['dividendenrendite'] = ''
                        os.remove(pdf_path)
                    else:
                        etf['dividendenrendite'] = ''
                else:
                    etf['dividendenrendite'] = ''
            except TimeoutException:
                logging.error("Could not find the 'Factsheet (DE)' link on the ETF profile page using specific XPath.")
                etf['dividendenrendite'] = ''
            except Exception as e:
                logging.error(f"An error occurred while trying to find/navigate to the Factsheet link: {e}")
                etf['dividendenrendite'] = ''

        # Step 3: Save all ETF data to a .txt file
    #     save_etf_data_to_txt(etf_rows, 'etf_ausschuettend.txt')
    #     print(f"Saved {len(etf_rows)} Ausschütt ETF entries to etf_ausschuettend.txt")

    except WebDriverException as e:
        logging.error(f"Selenium WebDriver error: {e}")
        print(f"Selenium error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
    finally:
        if driver:
            logging.info("Closing WebDriver.")
            driver.quit()

    insert_etf_entries(etf_rows, SUPABASE_URL)

if __name__ == "__main__":
    scrape_etf_links()

