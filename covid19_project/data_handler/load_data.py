import pandas as pd
import os
from django.conf import settings  # Import Django settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define the absolute path to the data directory using Django's settings
DATA_DIR = os.path.join(settings.BASE_DIR, 'data')

# Log statements for troubleshooting, to confirm absolute path is correct
logging.info("Current working directory: %s", os.getcwd())
logging.info("Data directory path: %s", DATA_DIR)


def load_and_process_data(file_path):
    """
    Loads and processes a CSV file with date parsing and optional FIPS handling.

    Parameters:
        file_path (str): The full path to the CSV file to load.

    Returns:
        pd.DataFrame or None: The processed DataFrame, or None if an error occurs.
    """
    logging.info("Loading data from: %s", file_path)

    try:
        # Load the dataset
        df = pd.read_csv(file_path)

        # Convert 'date' column to datetime format if it exists
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        # Fill missing FIPS values with 0 if 'fips' column exists
        if 'fips' in df.columns:
            df['fips'] = df['fips'].fillna(0)

        logging.info("Data loaded successfully from: %s", file_path)
        return df

    except FileNotFoundError:
        logging.error("File not found: %s", file_path)
        return None
    except Exception as e:
        logging.error("An error occurred while loading data: %s", e)
        return None

# Define filenames
FILENAMES = {
    "county": "us-counties.csv",
    "state": "us-states.csv",
    "us": "us.csv"
}

# Load data using absolute paths
county_data = load_and_process_data(os.path.join(DATA_DIR, FILENAMES["county"]))
state_data = load_and_process_data(os.path.join(DATA_DIR, FILENAMES["state"]))
us_data = load_and_process_data(os.path.join(DATA_DIR, FILENAMES["us"]))