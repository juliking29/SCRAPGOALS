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
from selenium.webdriver.chrome.service import Service as ChromeService # Importante para especificar chromedriver_path si es necesario
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
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Fallback for Windows if needed
        except locale.Error:
            print("Warning: Could not set Spanish locale for month parsing. Using default.")
            locale.setlocale(locale.LC_TIME, '') # Use system default

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="El Grafico Goalscorer Scraper API (Selenium)",
    description="API to scrape goalscorer data from El Grafico articles using Selenium.",
    version="1.3.0" # Version bump
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Variables de Entorno (Leídas desde el Dockerfile) ---
CHROME_BINARY_PATH = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome-stable')
CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')

def verify_chrome_versions():
    """Verify Chrome and ChromeDriver versions match."""
    try:
        # Get Chrome version
        chrome_version_output = subprocess.check_output(
            [CHROME_BINARY_PATH, '--version'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip()
        chrome_version = chrome_version_output.split()[-1]
        print(f"Detected Chrome version: {chrome_version} at {CHROME_BINARY_PATH}")

        # Get ChromeDriver version
        chromedriver_version_output = subprocess.check_output(
            [CHROMEDRIVER_PATH, '--version'],
            stderr=subprocess.STDOUT
        ).decode('utf-8').strip()
        # Output format is like: ChromeDriver 136.0.7103.92 (....)
        chromedriver_version = chromedriver_version_output.split()[1]
        print(f"Detected ChromeDriver version: {chromedriver_version} at {CHROMEDRIVER_PATH}")

        # Compare major versions
        if chrome_version.split('.')[0] != chromedriver_version.split('.')[0]:
            print(
                f"CRITICAL Version mismatch! Chrome major version {chrome_version.split('.')[0]} "
                f"does not match ChromeDriver major version {chromedriver_version.split('.')[0]}."
            )
            return False
        print("Chrome and ChromeDriver versions appear compatible.")
        return True
    except FileNotFoundError as e:
        print(f"Error finding Chrome or Chromedriver executable: {e}")
        print(f"Checked paths: Chrome='{CHROME_BINARY_PATH}', ChromeDriver='{CHROMEDRIVER_PATH}'")
        return False
    except Exception as e:
        print(f"Version check failed with unexpected error: {str(e)}")
        print(traceback.format_exc())
        return False

@app.on_event("startup")
async def startup_event():
    """Run version verification on startup."""
    if not verify_chrome_versions():
        print("Warning: Chrome/ChromeDriver version issues detected. WebDriver initialization might fail.")
        # Consider raising an exception or handling this more gracefully if needed
        # raise RuntimeError("Incompatible Chrome/ChromeDriver versions detected on startup.")

def init_driver():
    """Initializes and returns a Selenium WebDriver instance."""
    print("Initializing Selenium WebDriver...")
    chrome_options = ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--headless=new') # Use the new headless mode
    chrome_options.add_argument('--disable-gpu') # Often needed in headless environments
    chrome_options.add_argument('--window-size=1920x1080') # Specify window size
    chrome_options.add_argument('--remote-debugging-port=9222') # Optional for debugging

    # --- Opciones Anti-Detección ---
    chrome_options.add_argument('--disable-blink-features=AutomationControlled') # Evita detección básica
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # Establecer un User-Agent común
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    # -------------------------------

    # Especifica la ruta de Chrome (leída desde ENV)
    chrome_options.binary_location = CHROME_BINARY_PATH
    print(f"Using Chrome binary at: {CHROME_BINARY_PATH}")

    # Especifica la ruta de Chromedriver (leída desde ENV)
    # Usar Service es la forma moderna y recomendada
    service = ChromeService(executable_path=CHROMEDRIVER_PATH)
    print(f"Using ChromeDriver at: {CHROMEDRIVER_PATH}")

    try:
        print("Attempting to start WebDriver...")
        # Pass both service and options
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        print(f"WebDriverException during initialization: {e}")
        # Log specific errors often seen
        if "net::ERR_CONNECTION_REFUSED" in str(e):
            print("Error suggests Chrome process might not be starting correctly or port conflict.")
        elif "session not created" in str(e):
             print("Error 'session not created' often indicates version mismatch or resource issues.")
        elif "path to the driver executable" in str(e):
             print(f"Error indicates issue with Chromedriver path: '{CHROMEDRIVER_PATH}'. Check permissions and existence.")
        else:
            print(traceback.format_exc()) # Print full traceback for other errors
        return None
    except Exception as e:
        print(f"Unexpected error initializing Chrome: {e}")
        print(traceback.format_exc())
        return None

def extract_month_from_heading(heading_text):
    """Extracts month name from heading string (case-insensitive)."""
    # Improved regex to handle variations and be case-insensitive
    month_pattern = r'(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)'
    match = re.search(f'(?:MES DE |{month_pattern})', heading_text.upper())
    if match:
        # Find the actual month name within the match
        month_match = re.search(month_pattern, match.group(0))
        if month_match:
            return month_match.group(0).lower() # Return lowercase month name
    return None

def parse_table(table_element, is_monthly=False):
    """Parses an HTML table element into a list of dictionaries."""
    if not table_element:
        return None, "Table element not found."

    data_list = []
    # Find tbody, fallback to table itself if no tbody
    tbody = table_element.find('tbody') or table_element
    rows = tbody.find_all('tr')

    if not rows:
        return None, "No rows (<tr>) found in table body."

    # --- Header Detection Logic ---
    # More robust header detection needed, current logic is basic
    # For now, assume first row is header if it looks like one, otherwise data
    potential_header_row = rows[0]
    potential_header_cells = potential_header_row.find_all(['th', 'td']) # Look for <th> or <td>

    # Define expected headers (lowercase, no accents for matching)
    expected_headers_overall_norm = ['#', 'jugador', 'pais', 'equipo', 'goles', 'pj', 'promedio']
    expected_headers_monthly_norm = ['jugador', 'pais', 'equipo', 'goles', 'pj', 'promedio']

    headers_norm = [] # Normalized headers found
    header_map = {} # Map normalized header to original text
    data_start_index = 0 # Which row index data starts from

    if potential_header_cells:
        cell_texts_norm = [cell.text.strip().lower().replace('í', 'i') for cell in potential_header_cells] # Normalize

        # Check if it matches expected patterns
        is_overall_header = not is_monthly and len(cell_texts_norm) >= 7 and cell_texts_norm[0] == '#' and 'jugador' in cell_texts_norm[1]
        is_monthly_header = is_monthly and len(cell_texts_norm) >= 6 and 'jugador' in cell_texts_norm[0] and 'pais' in cell_texts_norm[1]

        if is_overall_header:
            headers_norm = expected_headers_overall_norm
            data_start_index = 1
            # Create map from normalized to original text (use first 7 cells)
            header_map = {norm_h: potential_header_cells[i].text.strip() for i, norm_h in enumerate(headers_norm)}
            print("Detected overall header row.")
        elif is_monthly_header:
            headers_norm = expected_headers_monthly_norm
            data_start_index = 1
             # Create map from normalized to original text (use first 6 cells)
            header_map = {norm_h: potential_header_cells[i].text.strip() for i, norm_h in enumerate(headers_norm)}
            print("Detected monthly header row.")
        else:
            print(f"Warning: First row doesn't strongly match expected headers. Assuming it's data. Raw text: {[c.text.strip() for c in potential_header_cells]}")
            # Assume default headers if first row doesn't look like a header
            headers_norm = expected_headers_monthly_norm if is_monthly else expected_headers_overall_norm
            header_map = {h: h.capitalize() for h in headers_norm} # Use normalized as keys and capitalized as values
            data_start_index = 0
    else:
         print("Warning: No cells found in the first row. Cannot determine headers.")
         return None, "No cells found in the first row."

    # --- Data Row Parsing ---
    data_rows = rows[data_start_index:]
    print(f"Parsing {len(data_rows)} data rows using headers: {headers_norm}")

    for i, row in enumerate(data_rows):
        cols = row.find_all('td') # Data rows should use <td>
        expected_col_count = len(headers_norm)

        if not cols or len(cols) < expected_col_count:
            print(f"Skipping row {data_start_index + i}: Expected {expected_col_count} columns, found {len(cols)}. Data: {[c.text.strip() for c in cols]}")
            continue

        item = {}
        col_texts = [ele.text.strip() for ele in cols]

        try:
            for idx, header_key_norm in enumerate(headers_norm):
                 # Use the original header text from the map if available, otherwise use normalized capitalized
                display_header = header_map.get(header_key_norm, header_key_norm.capitalize())
                item[display_header] = col_texts[idx] # Assign value using the display header

        except IndexError:
            print(f"Error processing row {data_start_index + i} due to IndexError. Data: {col_texts}")
            continue # Skip row on error

        # Basic validation: check if essential fields are present (optional)
        # if 'Jugador' not in item or not item.get('Jugador'):
        #    print(f"Warning: Row {data_start_index + i} seems incomplete. Data: {item}")

        data_list.append(item)

    if not data_list:
        return None, "Table found, but no data rows could be parsed successfully."

    print(f"Successfully parsed {len(data_list)} data entries from table.")
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
        "errors": [],
        "debug_info": {
            "page_title": None,
            "final_url": None,
        }
    }
    driver = None # Initialize driver to None

    try:
        driver = init_driver()
        if not driver:
            error_msg = "Failed to initialize Selenium WebDriver. Check logs for details."
            result["errors"].append(error_msg)
            # Use 503 Service Unavailable as WebDriver couldn't start
            raise HTTPException(status_code=503, detail=error_msg)

        print(f"Navigating to URL: {url}")
        driver.get(url)
        result["debug_info"]["final_url"] = driver.current_url # Store final URL after potential redirects

        # *** INCREASED TIMEOUT and CHANGED WAIT CONDITION ***
        wait_time = 90 # Increased timeout to 90 seconds
        print(f"Waiting up to {wait_time} seconds for page body to be present...")
        try:
            # Wait for the body tag to be present - more reliable than specific elements sometimes
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            print("Page body is present. Waiting a bit longer for dynamic content...")
            # Add a small explicit wait AFTER the body is present for JS to potentially load
            time.sleep(5)
            result["debug_info"]["page_title"] = driver.title # Get title after load
            print(f"Page title: {driver.title}")

        except TimeoutException:
            error_msg = f"Timeout waiting for page body to load ({wait_time}s)."
            result["errors"].append(error_msg)
            print(error_msg)
            # --- Save Debug Info on Timeout ---
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_file = f"timeout_screenshot_{timestamp}.png"
            pagesource_file = f"timeout_page_source_{timestamp}.html"
            try:
                print(f"Saving screenshot to {screenshot_file}")
                driver.save_screenshot(screenshot_file)
                print(f"Saving page source to {pagesource_file}")
                with open(pagesource_file, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                result["errors"].append(f"Debug files saved: {screenshot_file}, {pagesource_file}")
                print("Debug files saved successfully.")
            except Exception as save_err:
                err_save = f"Could not save debug files: {save_err}"
                result["errors"].append(err_save)
                print(err_save)
            # --- End Debug Info ---
            # Use 504 Gateway Timeout as the target page didn't load in time
            raise HTTPException(status_code=504, detail=error_msg)
        except WebDriverException as e:
            error_msg = f"WebDriverException during page load/wait: {e}"
            result["errors"].append(error_msg)
            print(error_msg)
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=error_msg)


        # Now that the page is likely loaded, parse the content
        print("Parsing page content with BeautifulSoup...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Overall 2025 Table
        print("Looking for 'GOLEADORES DEL AÑO 2025' table...")
        # Find h2 case-insensitively and strip whitespace
        h2_overall = soup.find(lambda tag: tag.name == 'h2' and 'nota__inner-title' in tag.get('class', []) and 'GOLEADORES DEL AÑO 2025' in tag.get_text(strip=True).upper())

        if h2_overall:
            print("Found 'GOLEADORES DEL AÑO 2025' heading.")
            # Find the *next* table sibling
            overall_table_element = h2_overall.find_next_sibling('table')
            if overall_table_element:
                 print("Found table element after overall heading.")
                 overall_data, error = parse_table(overall_table_element, is_monthly=False)
                 if overall_data:
                     result["data"]["overall_2025"] = overall_data
                     print(f"Successfully parsed {len(overall_data)} overall entries.")
                 elif error:
                     err_parse = f"Overall table parsing error: {error}"
                     result["errors"].append(err_parse)
                     print(err_parse)
            else:
                 print("Warning: Found overall heading but no subsequent <table> tag.")
                 result["errors"].append("Overall heading found, but no table followed.")
        else:
            print("Could not find 'GOLEADORES DEL AÑO 2025' heading.")


        # Monthly Tables
        print("Looking for monthly tables...")
        # Find all h2 tags with the specific class
        monthly_headers = soup.find_all('h2', class_='nota__inner-title')
        found_monthly = False

        for h2_tag in monthly_headers:
            heading_text = h2_tag.get_text(strip=True)
            # Check if it looks like a monthly header (and not the overall one)
            is_potential_monthly = ("GOLEADORES DE" in heading_text.upper() or "GOLEADORES DEL MES DE" in heading_text.upper()) and "AÑO 2025" not in heading_text.upper()

            if is_potential_monthly:
                month_name = extract_month_from_heading(heading_text)
                if month_name:
                    print(f"Found potential table for month: {month_name.capitalize()}")
                    month_table_element = h2_tag.find_next_sibling('table')
                    if month_table_element:
                        print(f"Found table element after '{heading_text}' heading.")
                        month_data, error = parse_table(month_table_element, is_monthly=True)
                        if month_data:
                            result["data"]["monthly"][month_name] = month_data
                            found_monthly = True
                            print(f"Successfully parsed {len(month_data)} entries for {month_name}.")
                        elif error:
                            err_parse = f"Monthly table parsing error ({month_name}): {error}"
                            result["errors"].append(err_parse)
                            print(err_parse)
                    else:
                        print(f"Warning: Found monthly heading '{heading_text}' but no subsequent <table> tag.")
                        result["errors"].append(f"Monthly heading '{heading_text}' found, but no table followed.")

        if not found_monthly:
            print("No monthly goalscorer tables were successfully parsed.")
            # Add error only if overall was also empty
            if not result["data"]["overall_2025"]:
                 result["errors"].append("No monthly goalscorer data could be extracted.")

        if not result["data"]["overall_2025"] and not result["data"]["monthly"]:
             print("Warning: No goalscorer data (overall or monthly) could be extracted from the page.")
             # Ensure an error message reflects this if not already present
             if "No goalscorer data could be extracted." not in result["errors"] and "Overall table parsing error" not in str(result["errors"]) and "Monthly table parsing error" not in str(result["errors"]):
                 result["errors"].append("Failed to extract any goalscorer tables.")


    except HTTPException as http_exc:
        # Re-raise HTTPException to be handled by FastAPI
        print(f"HTTPException caught: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        error_msg = f"Unexpected scraping error: {str(e)}"
        result["errors"].append(error_msg)
        print(error_msg)
        print(traceback.format_exc())
        # Use 500 Internal Server Error for unexpected issues
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if driver:
            try:
                driver.quit()
                print("WebDriver closed successfully.")
            except Exception as e:
                print(f"Error closing WebDriver: {e}")


    # Check if any data was actually scraped
    if not result["data"]["overall_2025"] and not result["data"]["monthly"] and not result["errors"]:
        # If no data AND no errors were logged, add a generic error
         result["errors"].append("Scraping finished, but no goalscorer data was found on the page.")

    return result


@app.get("/")
def read_root():
    """Root endpoint with API info and status check."""
    status = "operational"
    if not verify_chrome_versions():
        status = "warning_chrome_version_mismatch"
    return {
        "message": "El Grafico Goalscorer Scraper API",
        "version": app.version,
        "endpoints": {
            "/scrape": "Scrape default El Grafico goalscorer URL",
            "/scrape_url?url=<target_url>": "Scrape specific El Grafico URL"
        },
        "status": status
    }

@app.get("/scrape")
def get_default_scrape():
    """Scrape the default El Grafico goalscorer URL."""
    default_url = "https://www.elgrafico.com.ar/articulo/la-jornada-esta-aqui/84923/como-esta-la-tabla-de-goleadores-del-anio-2025"
    print(f"Received request to scrape default URL: {default_url}")
    try:
        start_time = time.time()
        data = scrape_goalscorers(default_url)
        end_time = time.time()
        print(f"Scraping completed in {end_time - start_time:.2f} seconds.")
        # Add duration to debug info if needed
        data.setdefault("debug_info", {})["scrape_duration_seconds"] = round(end_time - start_time, 2)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
        # Log the exception before re-raising
        print(f"HTTPException in /scrape endpoint: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /scrape endpoint: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error during scraping: {str(e)}")

@app.get("/scrape_url")
def get_scrape_custom_url(url: str):
    """Scrape a specified El Grafico URL."""
    print(f"Received request to scrape custom URL: {url}")
    # Basic URL validation
    if not url or not url.startswith("https://www.elgrafico.com.ar/"):
        print(f"Invalid URL provided: {url}")
        raise HTTPException(status_code=400, detail="Invalid or missing URL. Must start with https://www.elgrafico.com.ar/")

    try:
        start_time = time.time()
        data = scrape_goalscorers(url)
        end_time = time.time()
        print(f"Scraping completed in {end_time - start_time:.2f} seconds for URL: {url}")
         # Add duration to debug info if needed
        data.setdefault("debug_info", {})["scrape_duration_seconds"] = round(end_time - start_time, 2)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
         # Log the exception before re-raising
        print(f"HTTPException in /scrape_url endpoint for {url}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /scrape_url endpoint for {url}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error during scraping: {str(e)}")

# --- Main block for running locally (optional) ---
# if __name__ == "__main__":
#     import uvicorn
#     print("Starting Uvicorn server locally...")
#     # Verify versions before starting server locally
#     if not verify_chrome_versions():
#          print("Exiting due to Chrome/ChromeDriver version issues.")
#          exit(1)
#     uvicorn.run(app, host="0.0.0.0", port=8000)
