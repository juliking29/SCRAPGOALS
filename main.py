import requests
from bs4 import BeautifulSoup
import json
import traceback
from datetime import datetime
import re
import locale
import time
import os
import subprocess

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Set locale for Spanish month parsing
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_CO.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
        except locale.Error:
            print("Warning: Could not set Spanish locale for month parsing. Using default.")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="El Grafico Goalscorer Scraper API (Selenium)",
    description="API to scrape goalscorer data from El Grafico articles using Selenium.",
    version="1.2.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_chrome_versions():
    """Verify Chrome and ChromeDriver versions match."""
    try:
        # Get Chrome version
        chrome_version = subprocess.check_output(
            ['google-chrome-stable', '--version'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip().split()[-1]
        
        # Get ChromeDriver version
        chromedriver_version = subprocess.check_output(
            ['chromedriver', '--version'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip().split()[1]
        
        print(f"Chrome version: {chrome_version}")
        print(f"ChromeDriver version: {chromedriver_version}")
        
        # Compare major versions
        if chrome_version.split('.')[0] != chromedriver_version.split('.')[0]:
            raise RuntimeError(
                f"Version mismatch! Chrome {chrome_version} requires ChromeDriver {chrome_version.split('.')[0]}.*"
            )
        return True
    except Exception as e:
        print(f"Version check failed: {str(e)}")
        return False

@app.on_event("startup")
async def startup_event():
    """Run version verification on startup."""
    if not verify_chrome_versions():
        print("Critical: Chrome and ChromeDriver versions don't match!")
        # Don't exit - let the init_driver handle it

def init_driver():
    """Initialize Chrome WebDriver in headless mode with version checks."""
    print("Initializing WebDriver...")
    
    chrome_options = ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--headless=new')  # New headless mode
    chrome_options.add_argument('--window-size=1920x1080')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36')
    
    # Configuraciones adicionales importantes
    chrome_options.binary_location = '/usr/bin/google-chrome-stable'
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        # Intento con Service explícito
        from selenium.webdriver.chrome.service import Service
        service = Service(executable_path='/usr/local/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully!")
        return driver
    except Exception as e:
        print(f"Error initializing WebDriver: {str(e)}")
        print(traceback.format_exc())
        return None

def extract_month_from_heading(heading_text):
    """Extracts month name from heading string."""
    match = re.search(r'(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)', heading_text.upper())
    if match:
        return match.group(0).lower()
    else:
        match = re.search(r'MES DE (\w+)', heading_text.upper())
        if match:
            return match.group(1).lower()
    return None

def parse_table(table_element, is_monthly=False):
    """Parses an HTML table element into a list of dictionaries."""
    if not table_element:
        return None, "Table element not found."

    data_list = []
    tbody = table_element.find('tbody') or table_element
    rows = tbody.find_all('tr')

    if not rows:
        return None, "No rows found in table."

    header_row = rows[0]
    header_cells = header_row.find_all('td')

    if not header_cells:
        return None, "No cells found in the first row (potential header)."

    expected_headers_overall = ['#', 'jugador', 'país', 'equipo', 'goles', 'pj', 'promedio']
    expected_headers_monthly = ['jugador', 'país', 'equipo', 'goles', 'pj', 'promedio']

    headers = []
    header_texts_raw = [cell.text.strip().lower() for cell in header_cells]

    if not is_monthly and len(header_texts_raw) >= 7 and '#' in header_texts_raw[0] and 'jugador' in header_texts_raw[1]:
        headers = expected_headers_overall
        data_rows = rows[1:]
    elif is_monthly and len(header_texts_raw) >= 6 and 'jugador' in header_texts_raw[0] and 'país' in header_texts_raw[1]:
        raw_map = {
            'jugador': 'player',
            'país': 'country',
            'equipo': 'team',
            'goles': 'goals',
            'pj': 'matches_played',
            'promedio': 'average'
        }
        headers = [raw_map.get(h, h) for h in header_texts_raw[:6]]
        data_rows = rows[1:]
    else:
        print(f"Warning: Could not confidently identify header row. Assuming first row is data. Raw headers found: {header_texts_raw}")
        headers = expected_headers_monthly if is_monthly else expected_headers_overall
        data_rows = rows

    if not headers:
        return None, "Could not determine table headers."

    print(f"Using headers: {headers} for {'monthly' if is_monthly else 'overall'} table.")

    for i, row in enumerate(data_rows):
        cols = row.find_all('td')
        expected_col_count = len(headers)
        
        if not cols or len(cols) < expected_col_count:
            print(f"Skipping row {i+1}: Expected {expected_col_count} columns, found {len(cols)}. Data: {[c.text.strip() for c in cols]}")
            continue

        item = {}
        col_texts = [ele.text.strip() for ele in cols]

        try:
            for idx, header_key in enumerate(headers):
                if header_key == '#':
                    item['rank'] = col_texts[idx]
                else:
                    item[header_key] = col_texts[idx]
        except IndexError:
            print(f"Error processing row {i+1} due to IndexError. Data: {col_texts}")
            continue

        for key in headers:
            if key != '#' and key not in item:
                item[key] = None

        if any(v is None for k, v in item.items() if k != 'rank'):
            print(f"Warning: Row {i+1} has None values after mapping. Data: {item}")

        data_list.append(item)

    if not data_list:
        return None, "Table found, but no data rows could be parsed."

    return data_list, None

def scrape_goalscorers(url):
    """Scrapes goalscorer data using Selenium."""
    result = {
        "scraped_at": datetime.now().isoformat(),
        "source_url": url,
        "data": {
            "overall_2025": [],
            "monthly": {}
        },
        "errors": []
    }
    driver = None

    try:
        driver = init_driver()
        if not driver:
            error_msg = "Failed to initialize Selenium WebDriver."
            result["errors"].append(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        print(f"Fetching URL: {url}")
        driver.get(url)

        wait_time = 45
        print(f"Waiting up to {wait_time} seconds for page to load...")
        try:
            WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(@class, 'nota__inner-title')]"))
            )
            print("Page loaded successfully.")
            time.sleep(3)
        except TimeoutException:
            error_msg = f"Timeout waiting for page to load ({wait_time}s)."
            result["errors"].append(error_msg)
            try:
                driver.save_screenshot("timeout_screenshot.png")
                with open("timeout_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("Saved debug files for timeout.")
            except Exception as save_err:
                print(f"Could not save debug files: {save_err}")
            raise HTTPException(status_code=504, detail=error_msg)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Overall 2025 Table
        print("Looking for 'GOLEADORES DEL AÑO 2025' table...")
        h2_overall = soup.find('h2', class_='nota__inner-title', string='GOLEADORES DEL AÑO 2025')
        if h2_overall:
            overall_table_element = h2_overall.find_next_sibling('table')
            overall_data, error = parse_table(overall_table_element, is_monthly=False)
            if overall_data:
                result["data"]["overall_2025"] = overall_data
                print(f"Found {len(overall_data)} overall entries.")
            elif error:
                result["errors"].append(f"Overall table error: {error}")

        # Monthly Tables
        print("Looking for monthly tables...")
        monthly_headers = soup.find_all('h2', class_='nota__inner-title')
        found_monthly = False
        
        for h2_tag in monthly_headers:
            heading_text = h2_tag.get_text(strip=True)
            if ("GOLEADORES DE" in heading_text.upper() or "GOLEADORES DEL MES DE" in heading_text.upper()) and "AÑO 2025" not in heading_text.upper():
                month_name = extract_month_from_heading(heading_text)
                if month_name:
                    print(f"Found table for month: {month_name.capitalize()}")
                    month_table_element = h2_tag.find_next_sibling('table')
                    if month_table_element:
                        month_data, error = parse_table(month_table_element, is_monthly=True)
                        if month_data:
                            result["data"]["monthly"][month_name] = month_data
                            found_monthly = True
                            print(f"Found {len(month_data)} entries for {month_name}.")
                        elif error:
                            result["errors"].append(f"Monthly table error ({month_name}): {error}")

        if not found_monthly and not result["data"]["overall_2025"]:
            result["errors"].append("No goalscorer data could be extracted.")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Scraping error: {str(e)}"
        result["errors"].append(error_msg)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if driver:
            driver.quit()
            print("WebDriver closed.")

    return result

@app.get("/")
def read_root():
    """Root endpoint with API info."""
    return {
        "message": "El Grafico Goalscorer Scraper API",
        "endpoints": {
            "/scrape": "Scrape default El Grafico goalscorer URL",
            "/scrape_url?url=<target_url>": "Scrape specific El Grafico URL"
        },
        "status": "operational" if verify_chrome_versions() else "chrome_version_mismatch"
    }

@app.get("/scrape")
def get_default_scrape():
    """Scrape the default El Grafico goalscorer URL."""
    default_url = "https://www.elgrafico.com.ar/articulo/la-jornada-esta-aqui/84923/como-esta-la-tabla-de-goleadores-del-anio-2025"
    print(f"Scraping default URL: {default_url}")
    try:
        data = scrape_goalscorers(default_url)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scrape_url")
def get_scrape_custom_url(url: str):
    """Scrape a specified El Grafico URL."""
    if not url.startswith("https://www.elgrafico.com.ar/"):
        raise HTTPException(status_code=400, detail="Only elgrafico.com.ar URLs allowed.")
    
    print(f"Scraping custom URL: {url}")
    try:
        data = scrape_goalscorers(url)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))