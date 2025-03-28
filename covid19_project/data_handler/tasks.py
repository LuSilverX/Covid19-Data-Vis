import os
import time
import csv
import logging
from io import StringIO

from celery import shared_task
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .models import CDCData

logger = logging.getLogger(__name__)

@shared_task
def fetch_cdc_data(selected_state, selected_date):
    # Dictionary mapping states to their CDC codes
    state_codes = {
        "united states": "00",
        "alabama": "01",
        "alaska": "02",
        "arizona": "04",
        "arkansas": "05",
        "california": "06",
        "colorado": "08",
        "connecticut": "09",
        "delaware": "10",
        "district of columbia": "11",
        "florida": "12",
        "georgia": "13",
        "hawaii": "15",
        "idaho": "16",
        "illinois": "17",
        "indiana": "18",
        "iowa": "19",
        "kansas": "20",
        "kentucky": "21",
        "louisiana": "22",
        "maine": "23",
        "maryland": "24",
        "massachusetts": "25",
        "michigan": "26",
        "minnesota": "27",
        "mississippi": "28",
        "missouri": "29",
        "montana": "30",
        "nebraska": "31",
        "nevada": "32",
        "new hampshire": "33",
        "new jersey": "34",
        "new mexico": "35",
        "new york": "36",
        "north carolina": "37",
        "north dakota": "38",
        "ohio": "39",
        "oklahoma": "40",
        "oregon": "41",
        "pennsylvania": "42",
        "rhode island": "44",
        "south carolina": "45",
        "south dakota": "46",
        "tennessee": "47",
        "texas": "48",
        "utah": "49",
        "vermont": "50",
        "virginia": "51",
        "washington": "53",
        "west virginia": "54",
        "wisconsin": "55",
        "wyoming": "56",
        "new york city": "57",
    }

    # Determine the correct URL and state name
    selected_state = selected_state.lower()
    if selected_state and selected_state in state_codes:
        state_code = state_codes[selected_state]
        url = f"https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_{state_code}"
        state_name = selected_state.replace("united states", "United States").title()
    else:
        url = "https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_00"
        state_name = "United States"

    # Set up the download directory
    download_dir = os.path.join(os.getcwd(), "cdc_downloads")
    print("Download directory:", download_dir)
    os.makedirs(download_dir, exist_ok=True)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    csv_file_path = None

    try:
        logger.info(f"Navigating to {url}")
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Step 1: Switch to "Cumulative Deaths" view if needed
        try:
            logger.info("Looking for 'Weekly Deaths' dropdown...")
            weekly_deaths_dropdown = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Weekly Deaths')]"))
            )
            logger.info("Found 'Weekly Deaths' dropdown. Clicking...")
            weekly_deaths_dropdown.click()

            logger.info("Looking for 'Cumulative Deaths' option...")
            cumulative_option = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cumulative Deaths')]"))
            )
            logger.info("Found 'Cumulative Deaths'. Clicking...")
            cumulative_option.click()
        except Exception as e:
            logger.warning(f"Could not switch to 'Cumulative Deaths' view: {e}")
            logger.info("Continuing to next step...")

        # Step 2: Click the "Data Table for Cumulative Deaths" link
        logger.info("Looking for 'Data Table for Cumulative Deaths' link...")
        data_table_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[contains(text(), 'Data Table for Cumulative Deaths') and contains(text(), '{state_name}')]")
            )
        )
        logger.info("Found data table link. Scrolling into view and clicking...")
        driver.execute_script("arguments[0].scrollIntoView(true);", data_table_link)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", data_table_link)

        # Step 3: Check for a Tableau iframe and switch to it if present
        logger.info("Checking for Tableau iframe...")
        try:
            tableau_iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'tableau')]"))
            )
            driver.switch_to.frame(tableau_iframe)
            logger.info("Switched to Tableau iframe.")
        except Exception as e:
            logger.info(f"No Tableau iframe found: {e}")

        # Step 4: Locate the "Download Data" button
        logger.info("Looking for 'Download Data' button...")
        time.sleep(5)  # Pause to allow table data to load
        try:
            download_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "btnUSTrendsTableExport"))
            )
            logger.info("Found 'Download Data' button by ID.")
        except Exception as e:
            logger.warning(f"Failed to find 'Download Data' button by ID: {e}")
            download_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, 'data-table-container') and contains(@id, 'usTrends-table-container')]//button[contains(text(), 'Download Data')]")
                )
            )
            logger.info("Found 'Download Data' button via XPath.")

        # Step 5: Click the "Download Data" button
        driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", download_button)
        logger.info("Clicked 'Download Data' button.")

        # Step 6: Check for any new windows or tabs and handle them
        original_window = driver.current_window_handle
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                logger.info(f"Switched to new window/tab. URL: {driver.current_url}")
                time.sleep(5)  # Allow any actions to complete in the new tab
                driver.close()
                driver.switch_to.window(original_window)
                logger.info("Closed new window/tab and switched back to original window.")
                break

        # Step 7: Check for a modal (e.g., a Tableau dialog) offering CSV download
        try:
            logger.info("Checking for a modal...")
            modal = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog'], div.modal, div.tableau-dialog"))
            )
            logger.info("Modal found. Looking for CSV option...")
            csv_option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'CSV')]"))
            )
            driver.execute_script("arguments[0].click();", csv_option)
            logger.info("Clicked CSV option in modal.")
        except Exception as e:
            logger.info(f"No modal found or error interacting with modal: {e}")

        # Step 8: Switch back to the main content (if in an iframe)
        driver.switch_to.default_content()

        # Step 9: Pause to allow the download to initiate
        logger.info("Pausing for a few seconds to allow download to start...")
        time.sleep(15)

        # Step 10: Locate the most recently downloaded CSV file
        csv_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')]
        if csv_files:
            csv_file_path = max(csv_files, key=os.path.getctime)
            logger.info(f"CSV downloaded: {os.path.basename(csv_file_path)}")
        else:
            logger.error("No CSV file found in the download directory.")
            return

        # Read and process the CSV file
        print("Files in download directory:", os.listdir(download_dir))
        with open(csv_file_path, 'r') as f:
            csv_text = f.read()
        csv_file = StringIO(csv_text)
        reader = csv.DictReader(csv_file)

        # Save or update data in the database based on the selected date
        for row in reader:
            if selected_date and row.get('Date') != selected_date:
                continue
            state = row.get('Geography', state_name)
            date = row.get('Date', '')
            deaths_total = int(
                row.get('Cumulative Deaths', 0)
                if row.get('Cumulative Deaths') != "Counts 1-9" else 0
            )
            deaths_new = 0  # Placeholder: implement calculation if previous data is available

            CDCData.objects.update_or_create(
                state=state,
                date=date,
                defaults={
                    'deaths_total': deaths_total,
                    'deaths_new': deaths_new,
                }
            )
        logger.info(f"CDC data for {state_name} on {selected_date} processed successfully.")

    except Exception as e:
        logger.error(f"Failed to fetch CDC data for {state_name}: {e}")
    finally:
        driver.quit()
       # if csv_file_path and os.path.exists(csv_file_path):
      #      os.remove(csv_file_path)