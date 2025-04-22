import os
import time
import csv
import logging
from io import StringIO
from datetime import datetime
from celery import shared_task
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .models import CDCData

logger = logging.getLogger(__name__)

# --- Helper function to run the scrape logic for a single state ---
# This makes the main task cleaner, especially with the loop
def _scrape_and_save_state_data(state_key_to_process, state_codes):
    """Handles Selenium navigation, download, parsing, and saving for ONE state."""
    if state_key_to_process not in state_codes:
        logger.error(f"Invalid state key '{state_key_to_process}' passed to _scrape_and_save_state_data.")
        return False # Indicate failure

    state_code = state_codes[state_key_to_process]
    url = f"https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_{state_code}"
    state_name = state_key_to_process.replace("united states", "United States").title()
    logger.info(f"--- Processing state: {state_key_to_process} ---")

    # Set up download directory (consider making path absolute/configurable)
    download_dir = os.path.join(os.getcwd(), "cdc_downloads")
    logger.warning(f"Download directory: {download_dir}")
    os.makedirs(download_dir, exist_ok=True)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True # Corrected pref name
    }
    options.add_experimental_option("prefs", prefs)

    # Instantiate WebDriver INSIDE the function/loop for better isolation
    driver = webdriver.Chrome(options=options)
    csv_file_path = None
    success = False # Flag to track if processing succeeded for this state

    try:
        logger.info(f"Navigating to {url} for {state_key_to_process}")
        driver.get(url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # --- Selenium interactions ---
        # (Optional view switch - consider removing if problematic)
        try:
            logger.info("Looking for 'Weekly Deaths' dropdown...")
            weekly_deaths_dropdown = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Weekly Deaths')]")))
            logger.info("Found 'Weekly Deaths' dropdown. Clicking...")
            weekly_deaths_dropdown.click()
            logger.info("Looking for 'Cumulative Deaths' option...")
            cumulative_option = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cumulative Deaths')]")))
            logger.info("Found 'Cumulative Deaths'. Clicking...")
            cumulative_option.click()
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Could not switch view for {state_key_to_process} (might be okay): {e}")
            logger.info("Continuing...")

        logger.info("Looking for 'Data Table for Cumulative Deaths' link...")
        data_table_link = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), 'Data Table for Cumulative Deaths') and contains(text(), '{state_name}')]")))
        logger.info("Found data table link. Scrolling and clicking...")
        driver.execute_script("arguments[0].scrollIntoView(true);", data_table_link)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", data_table_link)
        time.sleep(3)

        # (Optional iframe switch)
        logger.info("Checking for Tableau iframe...")
        try:
            tableau_iframe = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'tableau')]")))
            logger.info("Switching to Tableau iframe.")
            driver.switch_to.frame(tableau_iframe)
        except Exception as e:
            logger.info(f"No Tableau iframe found or error: {e}")

        logger.info("Looking for 'Download Data' button...")
        time.sleep(5)
        download_button = None
        # (Simplified download button finding - adjust if needed)
        try:
             download_button = WebDriverWait(driver, 45).until(EC.element_to_be_clickable((By.ID, "btnUSTrendsTableExport")))
             logger.info("Found 'Download Data' button by ID 'btnUSTrendsTableExport'.")
        except Exception as e:
             logger.warning(f"Could not find button by ID 'btnUSTrendsTableExport', trying generic XPath: {e}")
             try:
                 download_button = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download Data')] | //a[contains(text(), 'Download Data')]")))
                 logger.info("Found 'Download Data' button via generic XPath.")
             except Exception as e2:
                 logger.error(f"COULD NOT FIND DOWNLOAD BUTTON for {state_key_to_process}: {e2}")
                 raise # Re-raise to stop processing this state

        logger.info("Scrolling download button...")
        driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
        time.sleep(1)
        logger.info("Clicking 'Download Data' button...")
        driver.execute_script("arguments[0].click();", download_button)
        logger.info("Clicked 'Download Data' button.")

        logger.info("Switching back to default content (if needed).")
        driver.switch_to.default_content()

        logger.info("Pausing for download...")
        time.sleep(20)

        logger.info(f"Checking download directory: {download_dir}")
        csv_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')]
        if not csv_files:
            logger.error(f"No CSV file found for {state_key_to_process} in {download_dir}")
            # Save screenshot for debugging no-download scenarios
            try:
                screenshot_path = os.path.join(download_dir, f'error_screenshot_{state_key_to_process}.png')
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
            except Exception as screen_e:
                 logger.error(f"Could not save screenshot: {screen_e}")
            return False # Indicate failure

        csv_file_path = max(csv_files, key=os.path.getctime)
        logger.info(f"Most recent CSV found: {os.path.basename(csv_file_path)}")

        # --- CSV Parsing and Saving ---
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                csv_text = f.read()
        except Exception as read_e:
             logger.error(f"Error reading CSV file {csv_file_path}: {read_e}")
             return False

        sample_lines = csv_text.strip().split('\n')[:5]
        logger.info(f"Sample CSV data: {sample_lines}")
        csv_lines = csv_text.strip().split('\n')
        if len(csv_lines) < 4:
            logger.error(f"CSV file '{os.path.basename(csv_file_path)}' doesn't have enough lines.")
            return False

        csv_file = StringIO('\n'.join(csv_lines[2:]))
        reader = csv.DictReader(csv_file)

        # Delete existing data for this state *before* processing rows
        logger.info(f"Clearing existing CDCData for state: {state_key_to_process}")
        count, _ = CDCData.objects.filter(state__iexact=state_key_to_process).delete()
        logger.info(f"Deleted {count} existing records for {state_key_to_process}")

        rows_processed = 0
        rows_skipped = 0
        date_formats = ["%b %d %Y", "%b %e %Y"]

        for row in reader:
            state_geo = row.get('Geography', '').lower()
            if state_geo != state_key_to_process: # Ensure row matches the state being processed
                logger.warning(f"Skipping row: Geo '{state_geo}' != Expected '{state_key_to_process}'")
                rows_skipped += 1
                continue

            date_str = row.get('Date', '').strip()
            data_as_of_str = row.get('Death Data As Of', '').strip()
            deaths_value = row.get('Cumulative Deaths', '0')

            parsed_date = None
            if date_str:
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError: continue
                if not parsed_date:
                    logger.warning(f"Date parse fail: '{date_str}' for {state_geo}. Skipping.")
                    rows_skipped += 1
                    continue

            parsed_data_as_of = None
            if data_as_of_str:
                 for fmt in date_formats:
                     try:
                         parsed_data_as_of = datetime.strptime(data_as_of_str, fmt).date()
                         break
                     except ValueError: continue
                 if not parsed_data_as_of:
                      logger.warning(f"DataAsOf parse fail: '{data_as_of_str}' for {state_geo} on {date_str}. Saving None.")

            deaths_total = 0
            if deaths_value == "Counts 1-9" or not deaths_value.strip():
                deaths_total = 0
            else:
                try:
                    deaths_total = int(deaths_value.replace(',', ''))
                except ValueError:
                    deaths_total = 0
                    logger.warning(f"Deaths parse fail: '{deaths_value}' for {state_geo} on {date_str}")

            if parsed_date:
                try:
                    obj, created = CDCData.objects.update_or_create(
                        state=state_geo,
                        date=parsed_date,
                        defaults={
                            'deaths_total': deaths_total,
                            'data_as_of': parsed_data_as_of # Assumes model allows null=True
                        }
                    )
                    rows_processed += 1
                except Exception as db_exc:
                     logger.error(f"DB error saving row {state_geo} on {parsed_date}: {db_exc}")
                     rows_skipped += 1

        logger.info(f"Data processing for {state_key_to_process}: {rows_processed} rows processed, {rows_skipped} rows skipped.")
        success = True # Mark as successful for this state

    except Exception as e:
        logger.exception(f"Unexpected error during scraping/processing for state {state_key_to_process}: {e}")
        success = False # Mark as failed
    finally:
        logger.info(f"Quitting WebDriver for state: {state_key_to_process}...")
        driver.quit()
        if csv_file_path and os.path.exists(csv_file_path):
            try:
                os.remove(csv_file_path)
                logger.info(f"Removed CSV: {os.path.basename(csv_file_path)}")
            except Exception as rm_exc:
                 logger.error(f"Error removing CSV {csv_file_path}: {rm_exc}")
        logger.info(f"--- Finished processing state: {state_key_to_process} (Success: {success}) ---")

    return success # Return status for this state

# --- Main Celery Task ---
@shared_task(bind=True) # Added bind=True for potential future use (e.g., retries)
def fetch_cdc_data(self, selected_state, selected_date): # Added self because of bind=True
    task_id = self.request.id # Get task ID for logging
    logger.error(f"!!!!!!!!!! fetch_cdc_data TASK STARTED (ID: {task_id}) for state: {selected_state} !!!!!!!!!!!")

    state_codes = {
        "united states": "00", "alabama": "01", "alaska": "02", "arizona": "04",
        "arkansas": "05", "california": "06", "colorado": "08", "connecticut": "09",
        "delaware": "10", "district of columbia": "11", "florida": "12", "georgia": "13",
        "hawaii": "15", "idaho": "16", "illinois": "17", "indiana": "18", "iowa": "19",
        "kansas": "20", "kentucky": "21", "louisiana": "22", "maine": "23",
        "maryland": "24", "massachusetts": "25", "michigan": "26", "minnesota": "27",
        "mississippi": "28", "missouri": "29", "montana": "30", "nebraska": "31",
        "nevada": "32", "new hampshire": "33", "new jersey": "34", "new mexico": "35",
        "new york": "36", "north carolina": "37", "north dakota": "38", "ohio": "39",
        "oklahoma": "40", "oregon": "41", "pennsylvania": "42", "rhode island": "44",
        "south carolina": "45", "south dakota": "46", "tennessee": "47", "texas": "48",
        "utah": "49", "vermont": "50", "virginia": "51", "washington": "53",
        "west virginia": "54", "wisconsin": "55", "wyoming": "56", "new york city": "57",
    }

    states_to_process = []
    if selected_state.lower() == 'all_states':
        # Get all state keys (excluding 'united states' for this example, add it back if needed)
        states_to_process = [state for state in state_codes.keys() if state != 'united states']
        logger.info(f"Task ID {task_id}: Scheduled run for ALL {len(states_to_process)} states.")
    elif selected_state.lower() in state_codes:
        states_to_process = [selected_state.lower()]
        logger.info(f"Task ID {task_id}: Triggered for single state: {selected_state}")
    else:
        logger.error(f"Task ID {task_id}: Invalid selected_state received: {selected_state}. Exiting.")
        return # Exit if state is invalid

    overall_success = True
    states_succeeded = 0
    states_failed = 0

    for current_state in states_to_process:
        # Call the helper function for each state
        # Using .s().apply_async() could distribute states to multiple workers if available,
        # but for simplicity here, we run sequentially within this task.
        # If one state fails, we log it but continue to the next.
        try:
            state_success = _scrape_and_save_state_data(current_state, state_codes)
            if state_success:
                 states_succeeded += 1
            else:
                 states_failed += 1
                 overall_success = False # Mark overall task as failed if any state fails
        except Exception as loop_exc:
             logger.exception(f"Task ID {task_id}: Unexpected error in loop for state {current_state}: {loop_exc}")
             states_failed += 1
             overall_success = False

        # Optional delay between states
        if len(states_to_process) > 1:
            logger.info(f"Task ID {task_id}: Pausing for 5 seconds before next state...")
            time.sleep(5)

    logger.info(f"Task ID {task_id}: Finished processing. Succeeded: {states_succeeded}, Failed: {states_failed}.")

    if not overall_success:
        raise Exception(f"Task {task_id} failed to process {states_failed} states.")
      # pass 

    # Main task function implicitly returns None