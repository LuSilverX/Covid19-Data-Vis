import os
import time
import csv
from collections import defaultdict
from django.conf import settings
import logging
from io import StringIO
from datetime import datetime
import requests 
from celery import shared_task
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .models import CDCData, WHOData

logger = logging.getLogger(__name__)

# Helper function for CDC scrape logic
def _scrape_and_save_state_data(state_key_to_process, state_codes):
    """Handles Selenium navigation, download, parsing, and saving for ONE CDC state."""
    if state_key_to_process not in state_codes:
        logger.error(f"Invalid state key '{state_key_to_process}' passed to _scrape_and_save_state_data.")
        return False # Indicating failure

    state_code = state_codes[state_key_to_process]
    url = f"https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_{state_code}"
    state_name = state_key_to_process.replace("united states", "United States").title()
    logger.info(f"--- Processing CDC state: {state_key_to_process} ---")

    # Setting up download directory 
    download_dir = settings.CDC_DOWNLOAD_DIR
    logger.warning(f"CDC Download directory: {download_dir}")
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

    driver = webdriver.Chrome(options=options)
    csv_file_path = None
    success = False # Flag to track if processing succeeded for this state

    try:
        logger.info(f"Navigating to {url} for {state_key_to_process}")
        driver.get(url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        logger.info("Looking for 'Data Table for Cumulative Deaths' link...")
        data_table_link = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), 'Data Table for Cumulative Deaths') and contains(text(), '{state_name}')]")))
        logger.info("Found data table link. Scrolling and clicking...")
        driver.execute_script("arguments[0].scrollIntoView(true);", data_table_link)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", data_table_link)
        time.sleep(3)

        logger.info("Looking for 'Download Data' button...")
        time.sleep(5)
        download_button = None
        # (Simplified download button finding - i may adjust if needed)
        try:
             # Trying the ID that worked before first
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
        time.sleep(4)

        logger.info(f"Checking download directory: {download_dir}")
        csv_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')]
        if not csv_files:
            logger.error(f"No CSV file found for {state_key_to_process} in {download_dir}")
            try:
                screenshot_path = os.path.join(download_dir, f'error_screenshot_cdc_{state_key_to_process}.png')
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
            except Exception as screen_e:
                 logger.error(f"Could not save screenshot: {screen_e}")
            return False # Indicate failure

        csv_file_path = max(csv_files, key=os.path.getctime)
        logger.info(f"Most recent CDC CSV found: {os.path.basename(csv_file_path)}")

        # CSV Parsing and Saving 
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                csv_text = f.read()
        except Exception as read_e:
             logger.error(f"Error reading CDC CSV file {csv_file_path}: {read_e}")
             return False

        sample_lines = csv_text.strip().split('\n')[:5]
        logger.info(f"Sample CDC CSV data: {sample_lines}")
        csv_lines = csv_text.strip().split('\n')
        if len(csv_lines) < 4:
            logger.error(f"CDC CSV file '{os.path.basename(csv_file_path)}' doesn't have enough lines.")
            return False

        csv_file = StringIO('\n'.join(csv_lines[2:]))
        reader = csv.DictReader(csv_file)

        # Deleting existing data for this state before processing rows
        logger.info(f"Clearing existing CDCData for state: {state_key_to_process}")
        count, _ = CDCData.objects.filter(state__iexact=state_key_to_process).delete()
        logger.info(f"Deleted {count} existing CDC records for {state_key_to_process}")

        rows_processed = 0
        rows_skipped = 0
        date_formats = ["%b %d %Y", "%b %e %Y"] # Expected formats like "Apr 12 2025" or "Apr  5 2025"

        for row_num, row in enumerate(reader):
            state_geo = row.get('Geography', '').lower()
            # Ensure the row matches the state thats processing
            if state_geo != state_key_to_process:
                 logger.warning(f"CDC Skipping row: Geo '{state_geo}' != Expected '{state_key_to_process}' in file {csv_file_path}")
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
                    logger.warning(f"CDC Date parse fail: '{date_str}' for {state_geo}. Skipping.")
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
                      logger.warning(f"CDC DataAsOf parse fail: '{data_as_of_str}' for {state_geo} on {date_str}. Saving None.")

            deaths_total = 0
            if deaths_value == "Counts 1-9" or not deaths_value.strip():
                deaths_total = 0
            else:
                try:
                    deaths_total = int(deaths_value.replace(',', ''))
                except ValueError:
                    deaths_total = 0
                    logger.warning(f"CDC Deaths parse fail: '{deaths_value}' for {state_geo} on {date_str}")

            if parsed_date:
                try:
                    obj, created = CDCData.objects.update_or_create(
                        state=state_geo,
                        date=parsed_date,
                        defaults={
                            'deaths_total': deaths_total,
                            'data_as_of': parsed_data_as_of # Model allows null=True
                        }
                    )
                    rows_processed += 1
                except Exception as db_exc:
                     logger.error(f"CDC DB error saving row {state_geo} on {parsed_date}: {db_exc}")
                     rows_skipped += 1

        logger.info(f"CDC data processing for {state_key_to_process}: {rows_processed} rows processed, {rows_skipped} rows skipped.")
        success = True # Mark as successful for this state

    except Exception as e:
        logger.exception(f"Unexpected error during CDC scraping/processing for state {state_key_to_process}: {e}")
        success = False # Mark as failed
    finally:
        logger.info(f"Quitting CDC WebDriver for state: {state_key_to_process}...")
        driver.quit()
        if csv_file_path and os.path.exists(csv_file_path):
            try:
                os.remove(csv_file_path)
                logger.info(f"Removed CDC CSV: {os.path.basename(csv_file_path)}")
            except Exception as rm_exc:
                 logger.error(f"Error removing CDC CSV {csv_file_path}: {rm_exc}")
        logger.info(f"--- Finished processing CDC state: {state_key_to_process} (Success: {success}) ---")

    return success # Returning status for this state


# Old main CDC Task because CDC changed its ui so no longer working
@shared_task(bind=True)
def fetch_cdc_data(self, selected_state, selected_date):
    task_id = self.request.id
    logger.info(f"!!!!!!!!!! fetch_cdc_data TASK STARTED (ID: {task_id}) for state: {selected_state} !!!!!!!!!!!")

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
        # Getting all state keys (including 'united states' for this example)
        states_to_process = list(state_codes.keys())
        logger.info(f"Task ID {task_id}: Scheduled CDC run for ALL {len(states_to_process)} states.")
    elif selected_state.lower() in state_codes:
        states_to_process = [selected_state.lower()]
        logger.info(f"Task ID {task_id}: CDC Triggered for single state: {selected_state}")
    else:
        logger.error(f"Task ID {task_id}: Invalid selected_state for CDC: {selected_state}. Exiting.")
        return

    overall_success = True
    states_succeeded = 0
    states_failed = 0

    for current_state in states_to_process:
        try:
            # Calling the helper function for each state
            state_success = _scrape_and_save_state_data(current_state, state_codes)
            if state_success:
                 states_succeeded += 1
            else:
                 states_failed += 1
                 overall_success = False
        except Exception as loop_exc:
             logger.exception(f"Task ID {task_id}: Unhandled error in CDC loop for state {current_state}: {loop_exc}")
             states_failed += 1
             overall_success = False

        # Optional delay between states if running 'all_states'
        if len(states_to_process) > 1:
            logger.info(f"Task ID {task_id}: Pausing 5 seconds before next CDC state...")
            time.sleep(5)

    logger.info(f"Task ID {task_id}: Finished CDC processing. Succeeded: {states_succeeded}, Failed: {states_failed}.")

    if not overall_success:
        Exception(f"Task {task_id} failed to process {states_failed} CDC states.")

# New main CDC Task for NCHS Weekly Deaths       
# Socrata CSV endpoint for:
# "Provisional COVID-19 Death Counts by Week Ending Date and State" (NCHS)
CDC_NCHS_DATASET_CSV = getattr(
    settings,
    "CDC_NCHS_DATASET_CSV",
    "https://data.cdc.gov/resource/r8kw-7aab.csv"
)

def _parse_date(value: str):
    """Parse YYYY-MM-DD or ISO strings like 2020-04-11T00:00:00.000 to date()."""
    if not value:
        return None
    v = value.strip()
    # If ISO with time, take date part
    if "T" in v:
        v = v.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None

@shared_task(bind=True)
def fetch_cdc_deaths_from_api_weekly(self, selected_state="all_states"):
    """
    OPTION A (current): Import *weekly* COVID-19 deaths from the NCHS dataset and store the
    weekly value in CDCData.deaths_total for each (state, week_ending_date).

    Should I later prefer cumulative instead, use OPTION B:
      - Compute a running sum per state from weekly counts and store that cumulative
        total into CDCData.deaths_total (no schema change required).

    OPTION C (alternative): Store *both* weekly and cumulative.
      - Add a new IntegerField CDCData.weekly_deaths via a migration.
      - Save weekly_deaths = weekly value from the dataset.
      - Save deaths_total  = cumulative (running sum) per state.
      - Preserves weekly detail while still supporting cumulative displays.
    """
    task_id = self.request.id
    logger.info(f"!!!!!!!!!! fetch_cdc_deaths_from_api_weekly START (ID: {task_id}) state={selected_state} !!!!!!!!!!!")

    headers = {}
    app_token = getattr(settings, "SOCRATA_APP_TOKEN", None)
    if app_token:
        headers["X-App-Token"] = app_token

    params = {
        "$limit": 50000,
        "$order": "state, week_ending_date",
        "$select": "state,week_ending_date,covid_19_deaths,data_as_of",
    }

    # If a single state was requested, filter to reduce payload.
    # Accepts 'united states' as a valid jurisdiction name.
    single = selected_state and selected_state.lower() not in ("all_states", "united states")
    if single:
        # Socrata accepts simple equality via field=query param for CSV.
        wanted = selected_state.title()
        params["$where"] = f"state='{wanted}'"

    try:
        resp = requests.get(CDC_NCHS_DATASET_CSV, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Task {task_id}: Error fetching NCHS CSV: {e}")
        return

    reader = csv.DictReader(StringIO(resp.text))
    if not reader.fieldnames:
        logger.error(f"Task {task_id}: NCHS CSV missing header")
        return

    # If we’re importing all states, we may want to start clean.
    if not single:
        deleted, _ = CDCData.objects.all().delete()
        logger.info(f"Task {task_id}: Cleared CDCData ({deleted} rows) before full import.")

    rows_upserted = 0
    per_week_us_sum = defaultdict(int)  # for building 'united states' if needed

    for row in reader:
        state_name = (row.get("state") or "").strip()
        week_str = (row.get("week_ending_date") or "").strip()
        das_str = (row.get("data_as_of") or "").strip()

        if not state_name or not week_str:
            continue

        # If user asked for one state, ignore others (CSV server-side filter *should* have done it)
        if single and state_name.lower() != selected_state.lower():
            continue

        week_date = _parse_date(week_str)
        if not week_date:
            continue

        try:
            weekly_deaths = int(str(row.get("covid_19_deaths", "0")).replace(",", "") or 0)
        except (TypeError, ValueError):
            weekly_deaths = 0

        data_as_of = _parse_date(das_str)

        # --- Option A decision point ---
        # We store the weekly count into 'deaths_total' for now.
        state_key = state_name.lower()
        CDCData.objects.update_or_create(
            state=state_key,
            date=week_date,
            defaults={
                "deaths_total": weekly_deaths,
                "data_as_of": data_as_of
            }
        )
        rows_upserted += 1

        # If we are doing a full import (all states), tally for a US row
        if not single and state_name.lower() != "united states":
            per_week_us_sum[week_date] += weekly_deaths

    # If full import and the dataset didn’t provide a 'United States' jurisdiction,
    # synthesize it by summing the states.
    if not single:
        for week_date, weekly_sum in per_week_us_sum.items():
            CDCData.objects.update_or_create(
                state="united states",
                date=week_date,
                defaults={
                    "deaths_total": weekly_sum,
                    "data_as_of": None
                }
            )
            rows_upserted += 1

    logger.info(f"Task {task_id}: Upserted ~{rows_upserted} weekly CDC rows (Option A).")
    logger.info(f"!!!!!!!!!! fetch_cdc_deaths_from_api_weekly FINISHED (ID: {task_id}) !!!!!!!!!!!")

# TASK for WHO Data 
@shared_task(bind=True)
def fetch_who_data(self):
    """
    Fetches the WHO global data CSV, parses it, and saves it to the WHOData model.
    Deletes old data before importing.
    """
    task_id = self.request.id
    logger.info(f"!!!!!!!!!! fetch_who_data TASK STARTED (ID: {task_id}) !!!!!!!!!!!")

    who_csv_url = "https://srhdpeuwpubsa.blob.core.windows.net/whdh/COVID/WHO-COVID-19-global-data.csv"
    rows_processed = 0
    rows_skipped = 0
    success = False

    try:
        # 1. Fetching the CSV data
        logger.info(f"Task {task_id}: Fetching WHO data from {who_csv_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(who_csv_url, headers=headers, timeout=30) # Longer timeout
        response.raise_for_status() # Checking for HTTP errors
        csv_text = response.text
        logger.info(f"Task {task_id}: Fetched {len(csv_text)} characters. Status: {response.status_code}")

        # 2. Prepare CSV Reader
        csv_file = StringIO(csv_text)
        # Checking header - can adjust expected headers if needed
        first_line = csv_file.readline()
        if 'Date_reported' not in first_line or 'Country' not in first_line or 'WHO_region' not in first_line:
             logger.error(f"Task {task_id}: WHO CSV headers missing/changed in first line: {first_line[:150]}")
             raise ValueError("WHO CSV Header mismatch")
        csv_file.seek(0) # Reset position for DictReader
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
             raise ValueError("Could not read WHO CSV header fieldnames")

        # 3. Clear existing WHO data from the database
        logger.info(f"Task {task_id}: Deleting existing WHOData records...")
        count, _ = WHOData.objects.all().delete()
        logger.info(f"Task {task_id}: Deleted {count} existing WHOData records.")

        # 4. Loop through CSV rows and save to model
        logger.info(f"Task {task_id}: Processing and saving new WHO data...")
        # Using individual create calls for simplicity, may consider bulk_create for performance on very large datasets
        # if performance becomes an issue later.

        for row_num, row in enumerate(reader):
            try:
                # Extract and clean data
                date_str = row.get('Date_reported', '').strip()
                country_code = row.get('Country_code', '').strip()
                country = row.get('Country', '').strip()
                who_region = row.get('WHO_region', '').strip()

                # Skip rows without essential data like date or country
                if not date_str or not country:
                    logger.warning(f"Task {task_id}: Skipping WHO row {row_num+2} due to missing date or country.")
                    rows_skipped += 1
                    continue

                # Parse date (YYYY-MM-DD)
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Task {task_id}: Invalid WHO date format '{date_str}' in row {row_num+2}. Skipping.")
                    rows_skipped += 1
                    continue

                # Parse integers, default to 0 if error or empty
                new_cases = 0
                try: new_cases = int(row.get('New_cases') or 0)
                except (ValueError, TypeError): pass # Handle potential None or non-int

                cumulative_cases = 0
                try: cumulative_cases = int(row.get('Cumulative_cases') or 0)
                except (ValueError, TypeError): pass

                new_deaths = 0
                try: new_deaths = int(row.get('New_deaths') or 0)
                except (ValueError, TypeError): pass

                cumulative_deaths = 0
                try: cumulative_deaths = int(row.get('Cumulative_deaths') or 0)
                except (ValueError, TypeError): pass

                # Create WHOData object (using create since i deleted all)
                WHOData.objects.create(
                    date_reported=parsed_date,
                    country_code=country_code,
                    country=country,
                    who_region=who_region,
                    new_cases=new_cases,
                    cumulative_cases=cumulative_cases,
                    new_deaths=new_deaths,
                    cumulative_deaths=cumulative_deaths
                )
                rows_processed += 1

                # Optional: Log progress periodically
                if rows_processed % 20000 == 0: # Log every 20k rows
                    logger.info(f"Task {task_id}: Processed {rows_processed} WHO rows...")

            except Exception as row_exc:
                # Log error for specific row but continue processing others
                logger.error(f"Task {task_id}: Error processing WHO CSV row {row_num+2}: {row_exc} - Data: {row}")
                rows_skipped += 1

        logger.info(f"Task {task_id}: Finished processing WHO data. Saved: {rows_processed}, Skipped: {rows_skipped}.")
        success = True

    except requests.exceptions.RequestException as req_e:
        logger.error(f"Task {task_id}: Network error fetching WHO data: {req_e}")
    except ValueError as val_e:
        logger.error(f"Task {task_id}: CSV format/parsing error for WHO data: {val_e}")
    except Exception as e:
        # Log other unexpected errors
        logger.exception(f"Task {task_id}: Unexpected error in fetch_who_data: {e}")

    #if not success:
        #raise Exception(f"Task {task_id} failed to fetch or process WHO data.")
        #pass

    logger.info(f"!!!!!!!!!! fetch_who_data TASK FINISHED (ID: {task_id}) !!!!!!!!!!!")