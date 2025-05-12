import json
import requests # Keep requests for potential fallback or other uses, though not primary now
from bs4 import BeautifulSoup
from datetime import datetime
import re
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time # Import time for potential waits if needed

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions # Rename to avoid conflict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- FastAPI Setup ---
app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Scraping Logic ---

def extract_table_data(table):
    """Extracts data from a BeautifulSoup table element."""
    headers = [th.text.strip() for th in table.find_all('th')]
    # Fallback if no 'th' tags are found directly
    if not headers and table.find('thead'):
        headers = [th.text.strip() for th in table.find('thead').find_all('th')]
    # Fallback if no 'th' or 'thead' found, try first row 'td' or 'th'
    if not headers and table.find('tr'):
        first_row_cells = table.find('tr').find_all(['td', 'th'])
        headers = [cell.text.strip() for cell in first_row_cells]

    rows = []
    tbody = table.find('tbody')
    if not tbody:
        print("Warning: No tbody found in table, trying direct tr search.")
        table_rows = table.find_all('tr')
        start_index = 0
        if headers and len(table_rows) > 0:
             first_row_content = [cell.text.strip() for cell in table_rows[0].find_all(['td', 'th'])]
             if headers == first_row_content:
                 start_index = 1
        for row in table_rows[start_index:]:
            cells = row.find_all('td')
            if cells:
                 rows.append([cell.text.strip() for cell in cells])
    else:
        for row in tbody.find_all('tr'):
            cells = row.find_all('td')
            if cells:
                rows.append([cell.text.strip() for cell in cells])

    # Create list of dictionaries
    data = []
    for row in rows:
        row_data = {}
        for header, cell_value in zip(headers, row):
             row_data[header] = cell_value
        if len(headers) > len(row):
            for i in range(len(row), len(headers)):
                row_data[headers[i]] = None
        if row_data:
            data.append(row_data)

    return data

def init_driver():
    """Initializes a headless Chrome WebDriver."""
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")  # Run without opening a browser window
    chrome_options.add_argument("--no-sandbox") # Necessary for running in some environments (like Docker)
    chrome_options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    chrome_options.add_argument("--disable-gpu") # Applicable to headless mode
    chrome_options.add_argument("--window-size=1920,1080") # Specify window size
    # Mimic a real user agent
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    # Optional: Specify chromedriver path if not in PATH
    # service = webdriver.chrome.service.Service(executable_path='/path/to/chromedriver')
    # driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        # Assumes chromedriver is in PATH
        driver = webdriver.Chrome(options=chrome_options)
        print("WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        print(f"Error initializing WebDriver: {e}")
        print("Ensure chromedriver is installed and in your PATH or specify its path.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during WebDriver initialization: {e}")
        return None


def scrape_goleadores_live(url):
    """Scrapes goalscorer data from the live URL using Selenium."""
    results = {
        "scraped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "source_url": url,
        "goleadores_anuales": [],
        "goleadores_enero": [],
        "goleadores_febrero": [],
        "goleadores_marzo": [],
        "error": None
    }
    driver = None # Initialize driver variable
    try:
        driver = init_driver()
        if not driver:
             results["error"] = "Failed to initialize WebDriver."
             return results

        print(f"Requesting URL with Selenium: {url}")
        driver.get(url)

        # Wait for a specific element that indicates the page (and tables) has loaded
        # Waiting for the presence of the first h2 title tag is a good indicator
        wait_time = 20 # Increased wait time
        print(f"Waiting up to {wait_time} seconds for content to load...")
        try:
             WebDriverWait(driver, wait_time).until(
                 EC.presence_of_element_located((By.CSS_SELECTOR, "h2.nota__inner-title"))
             )
             print("Content element (h2.nota__inner-title) found.")
             # Optional: Add a small delay after element is found, sometimes helps
             time.sleep(2)
        except TimeoutException:
             results["error"] = f"Page load timed out after {wait_time} seconds. Content might be blocked or structure changed."
             print(results["error"])
             # Save page source for debugging timeout issues
             try:
                 results["timed_out_page_content_snippet"] = driver.page_source[:500]
             except:
                 pass
             return results

        # Get page source after waiting and JavaScript execution
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Find all h2 tags which precede the tables
        h2_tags = soup.find_all('h2', class_='nota__inner-title')

        if not h2_tags:
             results["error"] = "No h2 tags with class 'nota__inner-title' found after page load. Structure might have changed or content is blocked."
             print(results["error"])
             return results

        # Iterate through each h2 tag to find its corresponding table
        tables_found = 0
        for h2 in h2_tags:
            title = h2.text.strip().upper()
            element = h2.find_next_sibling()
            table = None
            while element and not table:
                 if element.name == 'table':
                     table = element
                 elif element.find and element.find('table'):
                     table = element.find('table')
                 element = element.find_next_sibling()

            if table:
                tables_found += 1
                try:
                    table_data = extract_table_data(table)
                    if "GOLEADORES DEL AÑO 2025" in title:
                        results["goleadores_anuales"] = table_data
                    elif "TABLA DE GOLEADORES DE ENERO" in title:
                         results["goleadores_enero"] = table_data
                    elif "TABLA DE GOLEADORES DE FEBRERO" in title:
                         results["goleadores_febrero"] = table_data
                    elif "GOLEADORES DEL MES DE MARZO" in title:
                         results["goleadores_marzo"] = table_data
                    else:
                         print(f"Info: Skipping table with unrecognized title: {title}")
                except Exception as e_table:
                    print(f"Error processing table under h2 '{title}': {str(e_table)}")
                    print(traceback.format_exc())
            else:
                print(f"Warning: Could not find table following h2: {title}")

        if tables_found == 0 and not results["error"]:
             results["error"] = "Found h2 title tags but failed to find any subsequent tables. Page structure might differ from expected."
             print(results["error"])

    except WebDriverException as e_wd:
        error_msg = f"WebDriver error during scraping: {str(e_wd)}"
        print(error_msg)
        print(traceback.format_exc())
        results["error"] = error_msg
    except Exception as e:
        error_msg = f"General scraping error: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        results["error"] = error_msg
    finally:
        # Ensure the browser closes even if errors occur
        if driver:
            print("Closing WebDriver.")
            driver.quit()

    return results

# --- FastAPI Endpoints ---

@app.get("/")
def root():
    """Root endpoint providing a welcome message."""
    return {"message": "Servidor de Scraping de Goleadores - El Gráfico"}

@app.get("/scrape")
def get_goleadores():
    """Endpoint to trigger the scraping process and return data."""
    target_url = "https://www.elgrafico.com.ar/articulo/la-jornada-esta-aqui/84923/como-esta-la-tabla-de-goleadores-del-anio-2025"
    try:
        data = scrape_goleadores_live(target_url)
        if data.get("error"):
             return JSONResponse(content=data, status_code=500)
        return JSONResponse(content=data)
    except Exception as e:
        print("SERVER ERROR:", e)
        print(traceback.format_exc())
        return JSONResponse(content={
            "error": "An internal server error occurred.",
            "details": str(e),
            "trace": traceback.format_exc()
            }, status_code=500)

# --- Main execution (for running the server directly) ---
if __name__ == "__main__":
    import uvicorn
    print("To run the server, use: uvicorn <filename>:app --reload")
    # Example: uvicorn your_script_name:app --reload
    # uvicorn.run(app, host="0.0.0.0", port=8000) # Uncomment to run directly
