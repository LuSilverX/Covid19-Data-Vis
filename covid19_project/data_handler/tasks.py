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
from .models import CDCData  # Import the model

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

    # Determine the correct URL based on the user's input
    selected_state = selected_state.lower()
    if selected_state and selected_state in state_codes:
        state_code = state_codes[selected_state]
        url = f"https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_{state_code}"
        state_name = selected_state.replace("united states", "United States").title()
    else:
        # Default to overall US data
        url = "https://covid.cdc.gov/COVID-DATA-TRACKER/#trends_totaldeaths_select_00"
        state_name = "United States"

    # Configure Selenium to run headlessly and set download directory
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    download_dir = os.path.join(os.getcwd(), "cdc_downloads")
    os.makedirs(download_dir, exist_ok=True)
    prefs = {"download.default_directory": download_dir}
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        # Wait for the page body to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Click the dropdown menu labeled "Weekly Deaths"
        weekly_deaths_dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Weekly Deaths')]"))
        )
        weekly_deaths_dropdown.click()

        # Select the "Cumulative Deaths" option
        cumulative_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Cumulative Deaths')]"))
        )
        cumulative_option.click()

        # Scroll to and click the link that exposes the data table
        data_table_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), 'Data Table for Cumulative Deaths') and contains(text(), '{state_name}')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", data_table_link)
        data_table_link.click()

        # Wait for the "Data Download" button to become clickable, then click it
        download_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='Data Download']"))
        )
        download_button.click()

        # Pause to allow download to complete (adjust as needed)
        time.sleep(5)

        # Locate the most recently downloaded CSV file
        csv_file_path = max(
            [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')],
            key=os.path.getctime
        )

        # Read and process the CSV file
        with open(csv_file_path, 'r') as f:
            csv_text = f.read()
        csv_file = StringIO(csv_text)
        reader = csv.DictReader(csv_file)

        # Save data to the database
        for row in reader:
            if selected_date and row.get('Date') != selected_date:
                continue
            state = row.get('Geography', state_name)
            date = row.get('Date', '')
            deaths_total = int(row.get('Cumulative Deaths', 0) if row.get('Cumulative Deaths') != "Counts 1-9" else 0)
            deaths_new = 0  # Placeholder (calculate if previous data available)

            # Save or update the record in the database
            CDCData.objects.update_or_create(
                state=state,
                date=date,
                defaults={
                    'deaths_total': deaths_total,
                    'deaths_new': deaths_new,
                }
            )

    except Exception as e:
        logger.error(f"Failed to fetch CDC data for {state_name}: {e}")
    finally:
        driver.quit()
        if 'csv_file_path' in locals() and os.path.exists(csv_file_path):
            os.remove(csv_file_path)