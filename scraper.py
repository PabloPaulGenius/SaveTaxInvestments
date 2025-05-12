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
from handle_pdf import *
import os
import tempfile
import requests
import PyPDF2
import pdfplumber
import random

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('scraper.log', mode='w', encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.WARNING)  # Only show warnings/errors in console

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

URL = "https://www.justetf.com/de/etf-list-overview.html#aktien_digitalisierung"
BASE_URL = "https://www.justetf.com"
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 20
COOKIE_BUTTON_TEXT = "Auswahl erlauben"
MAX_TABLES = 1  # Maximum number of tables to process

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


def parse_tables(driver):
    """
    Parses up to MAX_TABLES tables on the page, logs the table name, number of rows, and number of 'Ausschütt' matches.
    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
    Returns:
        list of dict: Each dict contains ETF data for a row (columns 1-8, keys: 'name', 'ter', 'ytd', 'fondsgröße', 'auflagedatum', 'ausschüttung', 'replikation', 'isin', 'row', 'profile_url').
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    target_table_selector = "table.table.table-striped.dataTable.no-footer"
    data_tables = soup.select(target_table_selector)
    
    logging.info(f"Found {len(data_tables)} total tables on the page")
    if len(data_tables) > MAX_TABLES:
        logging.info(f"Limiting processing to first {MAX_TABLES} tables")
        data_tables = data_tables[:MAX_TABLES]
    
    etf_rows = []
    for table_index, table in enumerate(data_tables):
        if table_index >= MAX_TABLES:
            break
            
        # Find the closest previous <h3> tag for the table name
        table_name = None
        for prev in table.find_all_previous():
            if prev.name == 'h3':
                table_name = prev.get_text(strip=True)
                break
        if not table_name:
            table_name = f"Table {table_index+1}"  # fallback
            
        logging.info(f"\nProcessing {table_name} (Table {table_index + 1} of {min(len(data_tables), MAX_TABLES)})...")
        
        table_body = table.find('tbody')
        if not table_body:
            logging.warning(f"{table_name}: No tbody found. Skipping.")
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

def scroll_to_load_all_tables(driver):
    """
    Scrolls to the bottom of the page gradually to ensure all tables are loaded.
    Then scrolls back to top to ensure we can parse from the beginning.
    """
    logging.info("Starting gradual page scrolling to load all tables...")
    
    # Get initial page height
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Scroll down gradually
    scrolls = 0
    max_scrolls = 30  # Safety limit to prevent infinite loops
    
    while scrolls < max_scrolls:
        # Scroll down in steps of 800-1000 pixels
        driver.execute_script(f"window.scrollBy(0, {random.randint(800, 1000)});")
        time.sleep(0.5)  # Short pause between scrolls
        
        # Every few scrolls, wait a bit longer to let content load
        if scrolls % 5 == 0:
            logging.info(f"Completed {scrolls} scrolls, pausing to let content load...")
            time.sleep(2)
        
        # Check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # Try one more time with a longer wait
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logging.info("Reached the bottom of the page")
                break
        
        last_height = new_height
        scrolls += 1
    
    # Scroll back to top to ensure we can parse from the beginning
    logging.info("Scrolling back to top of the page...")
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)  # Wait for the page to stabilize
    
    # Count tables after scrolling
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    tables_count = len(soup.select("table.table.table-striped.dataTable.no-footer"))
    logging.info(f"After scrolling, found {tables_count} tables on the page")

def get_table_anchors(driver):
    """
    Finds all anchor elements that link to ETF tables (class 'light-link' and 'category-link').
    Returns a list of (anchor_element, anchor_text, anchor_href) tuples.
    """
    anchors = driver.find_elements(By.CSS_SELECTOR, 'a.light-link[category-link]')
    anchor_info = []
    for a in anchors:
        text = a.text.strip()
        href = a.get_attribute('href')
        anchor_info.append((a, text, href))
    logging.info(f"Found {len(anchor_info)} table anchor links.")
    return anchor_info


def parse_all_tables_by_anchors(driver, max_tables=MAX_TABLES):
    """
    Iterates over all table anchor links, clicks each, waits for the table to load, and parses it.
    Aggregates all ETF rows from all tables.
    """
    etf_rows = []
    anchors = get_table_anchors(driver)
    processed_tables = 0
    last_table_name = None
    for idx, (anchor, anchor_text, anchor_href) in enumerate(anchors):
        if processed_tables >= max_tables:
            break
        logging.info(f"\nJumping to table {idx+1}: {anchor_text} ({anchor_href})")
        try:
            driver.execute_script("arguments[0].click();", anchor)
        except Exception as e:
            logging.warning(f"Could not click anchor {anchor_text}: {e}")
            continue
        # Wait for the table to load (wait for h3 header to change or table to appear)
        try:
            WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                lambda d: anchor_text in d.page_source
            )
            time.sleep(1.5)  # Give extra time for table to render
        except Exception as e:
            logging.warning(f"Timeout waiting for table '{anchor_text}' to load: {e}")
            continue
        # Parse the table(s) now visible
        table_rows = parse_tables(driver)
        # Only add new tables (avoid duplicates if anchors point to same table)
        new_rows = [row for row in table_rows if row.get('table_name') != last_table_name]
        if new_rows:
            last_table_name = new_rows[0].get('table_name')
            etf_rows.extend(new_rows)
            processed_tables += 1
    logging.info(f"Total tables processed: {processed_tables}")
    return etf_rows

def scrape_etf_links():
    """
    Main scraping function. Iterates over all table anchors, collects Ausschütt ETF rows, downloads their factsheets, extracts Dividendenrendite, and saves all data to a .txt file.
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
        
        # Instead of scrolling, iterate over all table anchors and parse each table
        etf_rows = parse_all_tables_by_anchors(driver, max_tables=MAX_TABLES)
        if not etf_rows:
            print("No Ausschütt ETFs found in tables.")
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

