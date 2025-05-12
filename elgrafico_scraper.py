# ... (Keep all imports, locale settings, FastAPI app setup, CORS, init_driver, parse_table, extract_month_from_heading the same) ...
import requests
from bs4 import BeautifulSoup
import json
import traceback
from datetime import datetime
import re
import locale
import time
import os # Import os to potentially specify webdriver path

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions # Renamed to avoid conflict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try setting locale (remains the same)
# ... (locale setting code) ...
try:
    # Common Spanish locales
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_CO.UTF-8') # Colombia specific
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Windows specific
        except locale.Error:
             print("Warning: Could not set Spanish locale for month parsing. Using default.")


from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="El Grafico Goalscorer Scraper API (Selenium)",
    description="API to scrape goalscorer data from El Grafico articles using Selenium.",
    version="1.1.1" # Incremented version
)

# CORS Configuration (remains the same)
# ... (CORS middleware code) ...
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# --- Selenium WebDriver Initialization ---
def init_driver():
    """Initialize Chrome WebDriver in headless mode."""
    print("Initializing WebDriver...")
    chrome_options = ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920x1080')
    # Using a common user agent
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    # Disable logging clutter from Selenium/Chrome
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--log-level=3') # Suppress logs further


    # --- IMPORTANT: WebDriver Path ---
    # Option 1: Assume chromedriver is in PATH (common setup)
    try:
         # Adding service object explicitly can sometimes help, even for PATH
         service = webdriver.chrome.service.Service()
         driver = webdriver.Chrome(service=service, options=chrome_options)
         print("WebDriver initialized successfully (using Service, assumed from PATH).")
         return driver
    except WebDriverException as e:
         print(f"WebDriverException assuming PATH failed: {e}")
         # Option 2: Explicitly specify the path (Uncomment and modify if needed)
         # webdriver_path = '/path/to/your/chromedriver' # <--- CHANGE THIS PATH
         # webdriver_path = 'C:\\path\\to\\your\\chromedriver.exe' # Windows example
         # if not os.path.exists(webdriver_path):
         #     print(f"ERROR: WebDriver not found at specified path: {webdriver_path}")
         #     return None
         # try:
         #     service = webdriver.chrome.service.Service(executable_path=webdriver_path)
         #     driver = webdriver.Chrome(service=service, options=chrome_options)
         #     print(f"WebDriver initialized successfully from path: {webdriver_path}")
         #     return driver
         # except WebDriverException as e_path:
         #      print(f"WebDriverException using explicit path failed: {e_path}")
         #      print("Please ensure ChromeDriver is installed and accessible.")
         #      return None
         # except Exception as e_gen:
         #      print(f"Generic Exception during WebDriver initialization: {e_gen}")
         #      return None

         # If PATH failed and explicit path is commented out/failed
         print("Could not initialize WebDriver. Ensure ChromeDriver is in your PATH or specify the path in the script.")
         return None
    except Exception as e_outer:
         print(f"Unexpected error during WebDriver initialization: {e_outer}")
         print(traceback.format_exc())
         return None


# --- parse_table and extract_month_from_heading functions remain the same ---
# ... (paste the unchanged parse_table and extract_month_from_heading functions here) ...
def parse_table(table_element, is_monthly=False):
    """ Parses an HTML table element into a list of dictionaries. """
    if not table_element:
        return None, "Table element not found."

    data_list = []
    tbody = table_element.find('tbody')
    if not tbody:
         # Sometimes the table might not have a tbody, try finding rows directly in table
         tbody = table_element
    rows = tbody.find_all('tr')

    if not rows:
         return None, "No rows found in table."

    # Attempt to detect header row more robustly
    header_row = rows[0]
    header_cells = header_row.find_all('td') # El Grafico uses <td> for headers here

    if not header_cells:
         return None, "No cells found in the first row (potential header)."

    # Define expected headers based on type
    expected_headers_overall = ['#', 'jugador', 'país', 'equipo', 'goles', 'pj', 'promedio']
    expected_headers_monthly = ['jugador', 'país', 'equipo', 'goles', 'pj', 'promedio'] # Order might differ slightly

    headers = []
    header_texts_raw = [cell.text.strip().lower() for cell in header_cells]

    # Decide which header set to use based on the table type and cell content
    # Check based on specific content and column count where possible
    if not is_monthly and len(header_texts_raw) >= 7 and '#' in header_texts_raw[0] and 'jugador' in header_texts_raw[1]:
        headers = expected_headers_overall
        data_rows = rows[1:]
    elif is_monthly and len(header_texts_raw) >= 6 and 'jugador' in header_texts_raw[0] and 'país' in header_texts_raw[1]:
         # Adjusting monthly header detection - check content not just length
         # Need to map raw headers to standard keys
         raw_map = { # Map raw header text to standard keys
            'jugador': 'player',
            'país': 'country',
            'equipo': 'team',
            'goles': 'goals',
            'pj': 'matches_played',
            'promedio': 'average'
         }
         headers = [raw_map.get(h, h) for h in header_texts_raw[:6]] # Map only expected columns
         data_rows = rows[1:]
    else:
        # Fallback if header row isn't clear, assume first row is data
        print(f"Warning: Could not confidently identify header row. Assuming first row is data. Raw headers found: {header_texts_raw}")
        headers = expected_headers_monthly if is_monthly else expected_headers_overall # Guess based on context
        data_rows = rows # Process all rows as data


    if not headers:
        return None, "Could not determine table headers."

    print(f"Using headers: {headers} for {'monthly' if is_monthly else 'overall'} table.")

    for i, row in enumerate(data_rows):
        cols = row.find_all('td')
        # Use the length of the *determined* headers for comparison
        expected_col_count = len(headers)
        if not cols or len(cols) < expected_col_count:
            print(f"Skipping row {i+1}: Expected {expected_col_count} columns based on headers, found {len(cols)}. Data: {[c.text.strip() for c in cols]}")
            continue

        item = {}
        col_texts = [ele.text.strip() for ele in cols]

        # Map columns to headers carefully
        try:
            for idx, header_key in enumerate(headers):
                # Map based on the determined 'headers' list which now uses standard keys
                # For overall table, # needs special handling if headers list is standard
                if header_key == '#':
                    item['rank'] = col_texts[idx]
                else:
                    item[header_key] = col_texts[idx]

        except IndexError:
             print(f"Error processing row {i+1} due to IndexError. Data: {col_texts}")
             continue


        # Ensure all expected keys exist, even if mapping failed slightly (assign None)
        for key in headers:
             if key != '#' and key not in item:
                  item[key] = None

        # Check for None values after mapping
        if any(v is None for k, v in item.items() if k != 'rank'): # Ignore rank potentially being None
            print(f"Warning: Row {i+1} has None values after mapping. Data: {item}")
            # continue # Option to skip incomplete rows

        data_list.append(item)


    if not data_list:
        return None, "Table found, but no data rows could be parsed."

    return data_list, None

def extract_month_from_heading(heading_text):
    """ Extracts month name from heading string. """
    # Regex to find month names in Spanish within the heading
    match = re.search(r'(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)', heading_text.upper())
    if match:
        return match.group(0).lower()
    else:
        # Fallback for "MES DE X" format
        match = re.search(r'MES DE (\w+)', heading_text.upper())
        if match:
            return match.group(1).lower()
    return None # Return None if no month found


# --- Updated scrape_goalscorers function ---
def scrape_goalscorers(url):
    """
    Scrapes goalscorer data using Selenium with increased timeout and adjusted wait condition.
    """
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
            print(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        print(f"Attempting to fetch URL with Selenium: {url}")
        driver.get(url)

        # --- Wait for page elements to load ---
        # INCREASED TIMEOUT and CHANGED WAIT ELEMENT
        wait_time = 45 # Increased timeout significantly
        print(f"Waiting up to {wait_time} seconds for H2 title to load...")
        try:
            # Wait for the first H2 tag with the specific class name
            WebDriverWait(driver, wait_time).until(
                # EC.presence_of_element_located((By.CSS_SELECTOR, "h2.nota__inner-title")) # Wait for *any* h2 title
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(@class, 'nota__inner-title') and contains(text(), 'GOLEADORES DEL AÑO')]")) # Wait for specific overall title
            )
            print("H2 title found.")
            # Add a small fixed delay AFTER the element is found, just in case
            time.sleep(3)
        except TimeoutException:
            error_msg = f"Timeout waiting for H2 title element ({wait_time}s). Page might be slow, structure changed, or blocked."
            result["errors"].append(error_msg)
            print(error_msg)
            # Capture screenshot and source on timeout for debugging
            try:
                 driver.save_screenshot("timeout_screenshot.png")
                 with open("timeout_page_source.html", "w", encoding="utf-8") as f:
                      f.write(driver.page_source)
                 print("Debug files saved (timeout). **PLEASE CHECK THESE FILES!**")
            except Exception as save_err:
                 print(f"Could not save debug files: {save_err}")
            raise HTTPException(status_code=504, detail=error_msg)
        except Exception as wait_err:
             error_msg = f"Error during WebDriverWait: {wait_err}"
             result["errors"].append(error_msg)
             print(error_msg)
             raise HTTPException(status_code=500, detail=error_msg)

        # --- Get page source AFTER waiting and parse with BeautifulSoup ---
        page_source = driver.page_source
        if "<title>Cómo está la tabla de goleadores" not in page_source:
             print("Warning: Page source might not be the expected article content.")
             # Consider saving source if this warning appears often

        soup = BeautifulSoup(page_source, 'html.parser')
        print("HTML source obtained from Selenium and parsed.")

        # --- Parsing logic (remains the same) ---
        # Overall 2025 Table
        print("Looking for 'GOLEADORES DEL AÑO 2025' table...")
        h2_overall = soup.find('h2', class_='nota__inner-title', string='GOLEADORES DEL AÑO 2025')
        if h2_overall:
            overall_table_element = h2_overall.find_next_sibling('table')
            overall_data, error = parse_table(overall_table_element, is_monthly=False)
            if overall_data:
                result["data"]["overall_2025"] = overall_data
                print(f"Successfully parsed 'GOLEADORES DEL AÑO 2025' table. Found {len(overall_data)} entries.")
            elif error:
                result["errors"].append(f"Error parsing Overall 2025 table: {error}")
                print(f"Error parsing 'GOLEADORES DEL AÑO 2025' table: {error}")
            else:
                 result["errors"].append("Overall 2025 table element found but parsing failed unexpectedly.")
                 print("Overall 2025 table element found but parsing failed unexpectedly.")
        else:
            print("Warning: Could not find the 'GOLEADORES DEL AÑO 2025' heading.")

        # Monthly Tables
        print("Looking for monthly goalscorer tables...")
        monthly_headers = soup.find_all('h2', class_='nota__inner-title')
        found_monthly = False
        for h2_tag in monthly_headers:
            heading_text = h2_tag.get_text(strip=True)
            if ("GOLEADORES DE" in heading_text.upper() or "GOLEADORES DEL MES DE" in heading_text.upper()) and "AÑO 2025" not in heading_text.upper():
                month_name = extract_month_from_heading(heading_text)
                if month_name:
                    print(f"Found potential table for month: {month_name.capitalize()}")
                    month_table_element = h2_tag.find_next_sibling('table')
                    if month_table_element:
                        month_data, error = parse_table(month_table_element, is_monthly=True)
                        if month_data:
                            result["data"]["monthly"][month_name] = month_data
                            print(f"Successfully parsed table for {month_name.capitalize()}. Found {len(month_data)} entries.")
                            found_monthly = True
                        elif error:
                            error_msg = f"Error parsing table for {month_name.capitalize()}: {error}"
                            result["errors"].append(error_msg)
                            print(error_msg)
                        else:
                            error_msg = f"Table element for {month_name.capitalize()} found but parsing failed unexpectedly."
                            result["errors"].append(error_msg)
                            print(error_msg)
                    else:
                        print(f"Found heading for {month_name.capitalize()}, but no subsequent table element.")

        if not found_monthly and not result["data"]["overall_2025"]:
             print("No goalscorer tables were successfully parsed.")
             result["errors"].append("No goalscorer data could be extracted.")


    except WebDriverException as wd_e:
         error_msg = f"WebDriver error occurred: {str(wd_e)}"
         result["errors"].append(error_msg)
         print(error_msg)
         print(traceback.format_exc())
         raise HTTPException(status_code=500, detail=f"WebDriver Error: {error_msg}")
    except HTTPException as http_exc:
         # Re-raise HTTP exceptions we deliberately raised (like the timeout)
         raise http_exc
    except Exception as e:
        error_msg = f"An unexpected error occurred during scraping: {str(e)}"
        result["errors"].append(error_msg)
        print(error_msg)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if driver:
            print("Quitting WebDriver.")
            driver.quit()

    # Final check remains same
    if not result["data"]["overall_2025"] and not result["data"]["monthly"]:
        final_error = "Failed to scrape any goalscorer data. Page structure might have changed or tables are missing/unparseable."
        if not any(final_error in e for e in result["errors"]):
            result["errors"].append(final_error)
        print(final_error)

    return result


# --- API Endpoints --- (Remain the same)

@app.get("/")
def read_root():
    """ Root endpoint providing basic API information. """
    return {
        "message": "Welcome to the El Grafico Goalscorer Scraper API (Selenium)",
        "endpoints": {
            "/scrape": "GET request to scrape the default El Grafico goalscorer URL.",
            "/scrape_url?url=<target_url>": "GET request to scrape a specific El Grafico URL."
        }
    }

@app.get("/scrape")
def get_default_scrape():
    """ Scrapes the default El Grafico goalscorer URL using Selenium. """
    default_url = "https://www.elgrafico.com.ar/articulo/la-jornada-esta-aqui/84923/como-esta-la-tabla-de-goleadores-del-anio-2025"
    print(f"Received request for default URL: {default_url}")
    try:
        data = scrape_goalscorers(default_url)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        print(f"Error in /scrape endpoint: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error in endpoint: {str(e)}")


@app.get("/scrape_url")
def get_scrape_custom_url(url: str):
    """ Scrapes a specified El Grafico URL using Selenium. """
    print(f"Received request for custom URL: {url}")
    if not url.startswith("https://www.elgrafico.com.ar/"):
        raise HTTPException(status_code=400, detail="Invalid URL. Only 'elgrafico.com.ar' URLs are allowed.")

    try:
        data = scrape_goalscorers(url)
        return JSONResponse(content=data)
    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        print(f"Error in /scrape_url endpoint for {url}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error in endpoint: {str(e)}")

# Remember to run using: uvicorn your_filename:app --reload
# Ensure ChromeDriver is installed and accessible!