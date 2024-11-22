import pandas as pd
import os

# Define the absolute path to the data directory once, outside the function
DATA_DIR = os.path.join(os.getcwd(), 'data')

# Print statements for troubleshooting, to confirm absolute path is correct
print("Current working directory:", os.getcwd())
print("Data directory path:", DATA_DIR)


def load_and_process_data(file_path):
    """
    Loads and processes a CSV file with date parsing and optional FIPS handling.

    Parameters:
        file_path (str): The full path to the CSV file to load.

    Returns:
        pd.DataFrame: The processed DataFrame.
    """
    # Print the file path inside the function to verify
    print("Loading data from:", file_path)

    try:
        # Load the dataset
        df = pd.read_csv(file_path)

        # Convert 'date' column to datetime format if it exists
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        # Fill missing FIPS values with 0 if 'fips' column exists
        if 'fips' in df.columns:
            df['fips'].fillna(0, inplace=True)

        print("Data loaded successfully from:", file_path)
        return df

    except FileNotFoundError as e:
        print("FileNotFoundError:", e)
    except Exception as e:
        print("An error occurred while loading data:", e)


# Use absolute paths by combining DATA_DIR with each filename
county_data = load_and_process_data(os.path.join(DATA_DIR, 'us-counties.csv'))
state_data = load_and_process_data(os.path.join(DATA_DIR, 'us-states.csv'))
us_data = load_and_process_data(os.path.join(DATA_DIR, 'us.csv'))
