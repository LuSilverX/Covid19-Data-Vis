import os
import time
import csv
import logging
from io import StringIO
from datetime import datetime  # <-- ADDED: Import datetime
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
    logger.error("!!!!!!!!!! fetch_cdc_data TASK STARTED !!!!!!!!!!!")
    # Dictionary mapping states to their CDC codes
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

    # Determining the correct URL and state name
    selected_state_lower = selected_state.lower() # Use a different variable to preserve original case if needed later
    if selected_state_lower and selected_state_lower in state_codes:
        state_code = state_codes[selected_state_lower]
        url = f"https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_{state_code}"
        # Use original selected_state for display name if needed, otherwise use the lowercased one
        state_name = selected_state_lower.replace("united states", "United States").title()
    else:
        url = "https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_00"
        state_name = "United States"
        selected_state_lower = "united states" # Ensure consistency

    # Seting up the download directory
    # Use absolute path based on script location or settings if needed, os.getcwd() might vary depending on how celery runs
    # For simplicity, keeping os.getcwd() but consider making it more robust later.
    download_dir = os.path.join(os.getcwd(), "cdc_downloads")
    logger.warning(f"Download directory: {download_dir}") # Use warning level for visibility
    os.makedirs(download_dir, exist_ok=True)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    # Ensure the user running celery has write permissions to the download_dir
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safeBrowse.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    csv_file_path = None

    try:
        logger.info(f"Navigating to {url}")
        driver.get(url)
        # Maybe increase wait time if page loads slowly
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Step 1: Switch to "Cumulative Deaths" view (Optional - Consider removing if default is okay)
        # This section frequently timed out in logs, maybe comment it out if not strictly needed
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
            time.sleep(2) # Add a small pause after clicking
        except Exception as e:
            logger.warning(f"Could not switch to 'Cumulative Deaths' view (might be okay): {e}")
            logger.info("Continuing to next step...")

        # Step 2: Clicking the "Data Table for Cumulative Deaths" link
        logger.info("Looking for 'Data Table for Cumulative Deaths' link...")
        data_table_link = WebDriverWait(driver, 30).until( # Increased wait slightly
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[contains(text(), 'Data Table for Cumulative Deaths') and contains(text(), '{state_name}')]")
            )
        )
        logger.info("Found data table link. Scrolling into view and clicking...")
        driver.execute_script("arguments[0].scrollIntoView(true);", data_table_link)
        time.sleep(2) # Increased pause
        driver.execute_script("arguments[0].click();", data_table_link)
        time.sleep(3) # Pause after click for content to potentially load

        # Step 3: Check for a Tableau iframe and switch to it if present
        # This also timed out before, consider increasing wait or making logic more robust if needed
        logger.info("Checking for Tableau iframe...")
        try:
            tableau_iframe = WebDriverWait(driver, 15).until( # Increased wait
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'tableau')]"))
            )
            logger.info("Switching to Tableau iframe.")
            driver.switch_to.frame(tableau_iframe)
        except Exception as e:
            logger.info(f"No Tableau iframe found or error switching: {e}")

        # Step 4: Locate the "Download Data" button
        logger.info("Looking for 'Download Data' button...")
        time.sleep(5) # Keep pause for table data load
        download_button = None
        try:
            # Try finding button by specific ID first (potentially inside iframe)
            download_button = WebDriverWait(driver, 45).until( # Increased wait significantly
                 EC.element_to_be_clickable((By.ID, "download-data-link")) # Check if ID changed on CDC site? or btnUSTrendsTableExport?
             )
            logger.info("Found 'Download Data' button by ID 'download-data-link'.")
        except Exception:
             logger.warning("Could not find button by ID 'download-data-link', trying ID 'btnUSTrendsTableExport'.")
             try:
                 download_button = WebDriverWait(driver, 10).until( # Shorter wait for fallback
                     EC.element_to_be_clickable((By.ID, "btnUSTrendsTableExport"))
                 )
                 logger.info("Found 'Download Data' button by ID 'btnUSTrendsTableExport'.")
             except Exception as e:
                 logger.warning(f"Failed to find 'Download Data' button by ID: {e}. Trying generic XPath.")
                 # Fallback XPath (might need adjustment if site changed)
                 try:
                     download_button = WebDriverWait(driver, 10).until(
                          EC.element_to_be_clickable(
                              (By.XPATH, "//button[contains(text(), 'Download Data')] | //a[contains(text(), 'Download Data')]") # More generic
                          )
                     )
                     logger.info("Found 'Download Data' button via generic XPath.")
                 except Exception as e2:
                     logger.error(f"COULD NOT FIND DOWNLOAD BUTTON by any method: {e2}")
                     raise # Re-raise the exception if button not found

        # Step 5: Clicking the "Download Data" button
        logger.info("Scrolling download button into view...")
        driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
        time.sleep(1)
        logger.info("Clicking 'Download Data' button...")
        driver.execute_script("arguments[0].click();", download_button)
        logger.info("Clicked 'Download Data' button.")

        # --- Steps 6, 7, 8 for modals/new tabs seem okay, kept as is ---
        # Step 6: Checking for any new windows or tabs and handle them
        # (This might not be needed if download happens directly)
        # original_window = driver.current_window_handle
        # if len(driver.window_handles) > 1:
        #     logger.warning("Multiple windows detected after download click.")
        #     for window_handle in driver.window_handles:
        #         if window_handle != original_window:
        #             driver.switch_to.window(window_handle)
        #             logger.info(f"Switched to new window/tab. URL: {driver.current_url}. Closing it.")
        #             time.sleep(2) # Allow potential actions
        #             driver.close()
        #             driver.switch_to.window(original_window)
        #             logger.info("Closed new window/tab and switched back.")
        #             break

        # Step 7: Check for a modal offering CSV download
        # (This also might not be needed if direct download works)
        # try:
        #     logger.info("Checking for a download modal...")
        #     modal = WebDriverWait(driver, 7).until( # Slightly longer wait
        #         EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog'], div.modal, div.tableau-dialog"))
        #     )
        #     logger.info("Modal found. Looking for CSV option...")
        #     csv_option = WebDriverWait(driver, 5).until(
        #         EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'CSV')] | //button[contains(text(), 'CSV')]")) # Try button too
        #     )
        #     logger.info("Clicking CSV option in modal.")
        #     driver.execute_script("arguments[0].click();", csv_option)
        # except Exception as e:
        #     logger.info(f"No modal found or error interacting with modal: {e}")

        # Step 8: Switch back to the main content (if switched into an iframe earlier)
        # Make sure this runs even if iframe wasn't found
        logger.info("Switching back to default content (if needed).")
        driver.switch_to.default_content()

        # Step 9: Pausing to allow the download to initiate and complete
        logger.info("Pausing for download...")
        time.sleep(20) # Increased pause for download completion

        # Step 10: Locating the most recently downloaded CSV file
        logger.info(f"Checking download directory: {download_dir}")
        csv_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')]
        if csv_files:
            csv_file_path = max(csv_files, key=os.path.getctime)
            logger.info(f"Most recent CSV found: {os.path.basename(csv_file_path)}")
        else:
            logger.error(f"No CSV file found in the download directory: {download_dir}")
            # Attempt to take a screenshot for debugging
            try:
                 screenshot_path = os.path.join(download_dir, 'error_screenshot.png')
                 driver.save_screenshot(screenshot_path)
                 logger.info(f"Saved screenshot to {screenshot_path}")
            except Exception as screen_e:
                 logger.error(f"Could not save screenshot: {screen_e}")
            return # Exit task if no CSV found

        # Reading and processing the CSV file
        # Add encoding='utf-8-sig' to handle potential BOM (\ufeff)
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                csv_text = f.read()
        except Exception as read_e:
             logger.error(f"Error reading CSV file {csv_file_path}: {read_e}")
             return

        # Log sample data
        sample_lines = csv_text.strip().split('\n')[:5]
        logger.info(f"Sample CSV data: {sample_lines}")

        # Checking if the CSV contains headers and data
        csv_lines = csv_text.strip().split('\n')
        if len(csv_lines) < 4: # Title, date generated, headers, and at least one data row
            logger.error(f"CSV file '{os.path.basename(csv_file_path)}' doesn't contain expected data structure (needs at least 4 lines).")
            return

        # Use StringIO for DictReader, skipping first two lines
        csv_file = StringIO('\n'.join(csv_lines[2:]))
        reader = csv.DictReader(csv_file)

        # Clearing existing data for this state - Check if selected_date logic needed
        # This runs if selected_date is '' (empty string), which it is based on view call
        if not selected_date:
            logger.info(f"Clearing existing CDCData for state: {selected_state_lower}")
            count, _ = CDCData.objects.filter(state__iexact=selected_state_lower).delete()
            logger.info(f"Deleted {count} existing records for {selected_state_lower}")
        else:
             logger.info(f"Skipping delete for {selected_state_lower} because selected_date ('{selected_date}') was provided.")


        # Saving or updating data in the database
        rows_processed = 0
        rows_skipped = 0
        # Define expected date formats from CSV
        # Format might be "Apr  5 2025" (double space) or "Apr 5 2025" (single space)
        date_formats = ["%b %d %Y", "%b %e %Y"]

        for row in reader:
            # Get raw data
            state_geo = row.get('Geography', '').lower()
            date_str = row.get('Date', '').strip()
            data_as_of_str = row.get('Death Data As Of', '').strip()
            deaths_value = row.get('Cumulative Deaths', '0')

            # --- ADDED: Date Parsing Logic ---
            parsed_date = None
            if date_str:
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        break # Stop trying formats if one works
                    except ValueError:
                        continue # Try next format
                if not parsed_date:
                    logger.warning(f"Could not parse date '{date_str}' with any format for state {state_geo}. Skipping row.")
                    rows_skipped += 1
                    continue

            # --- ADDED: Data As Of Parsing Logic ---
            parsed_data_as_of = None
            if data_as_of_str:
                 for fmt in date_formats:
                     try:
                         parsed_data_as_of = datetime.strptime(data_as_of_str, fmt).date()
                         break
                     except ValueError:
                         continue
                 if not parsed_data_as_of:
                      logger.warning(f"Could not parse data_as_of '{data_as_of_str}' with any format for state {state_geo} on date {date_str}. Saving as NULL/None.")
                      # Set to None if parsing fails, assuming model allows null=True for data_as_of if it's DateField
                      # If data_as_of is still CharField, maybe save the original string or None

            # --- Date Filtering Logic (Using parsed_date now if selected_date exists) ---
            # Note: selected_date is passed as '' from the view, so this block won't run currently.
            # If you implement date filtering later, you'd need to parse selected_date too.
            if selected_date:
                 try:
                      filter_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date() # Assuming YYYY-MM-DD filter
                      if parsed_date != filter_date_obj:
                           rows_skipped += 1
                           continue
                 except ValueError:
                      logger.error(f"Invalid selected_date format: {selected_date}. Cannot filter.")
                      # Decide whether to stop or process all dates if filter is invalid

            # Handling special case for very small counts
            if deaths_value == "Counts 1-9" or not deaths_value.strip():
                deaths_total = 0
            else:
                try:
                    # Remove commas if present before converting to int
                    deaths_total = int(deaths_value.replace(',', ''))
                except ValueError:
                    deaths_total = 0
                    logger.warning(f"Could not convert deaths_value '{deaths_value}' to integer for {state_geo} on {date_str}")

            # --- MODIFIED: Creating or updating the record ---
            if parsed_date: # Ensure we have a valid date before saving
                try:
                    obj, created = CDCData.objects.update_or_create(
                        state=state_geo, # Use state from CSV row
                        date=parsed_date, # Use parsed date object
                        defaults={
                            'deaths_total': deaths_total,
                            # Use parsed date object if data_as_of is DateField, otherwise use string
                            'data_as_of': parsed_data_as_of # Use parsed data_as_of object
                        }
                    )
                    rows_processed += 1
                except Exception as db_exc:
                     # Catch potential database errors during save
                     logger.error(f"Database error saving row for {state_geo} on {parsed_date}: {db_exc}")
                     rows_skipped += 1

        logger.info(f"CDC data processing for {selected_state_lower}: {rows_processed} rows processed, {rows_skipped} rows skipped.")

    except Exception as e:
        # Log the full traceback for unexpected errors
        logger.exception(f"Unexpected error fetching CDC data for {selected_state}: {e}") # Use logger.exception
    finally:
        # Ensure driver quits even if errors occur
        logger.info("Quitting WebDriver...")
        driver.quit()
        # Clean up downloaded file
        if csv_file_path and os.path.exists(csv_file_path):
            try:
                os.remove(csv_file_path)
                logger.info(f"Removed downloaded CSV file: {os.path.basename(csv_file_path)}")
            except Exception as rm_exc:
                 logger.error(f"Error removing CSV file {csv_file_path}: {rm_exc}")