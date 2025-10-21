import os
import pandas as pd
import requests
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException  # Import this
import pygsheets
import json

def login(link, username, password):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-data-dir=/tmp/user-data-' + str(int(time.time())))
    
    download_dir = "/tmp"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowing.enabled": True
    }
    options.add_experimental_option('prefs', prefs)
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        driver.get(link)
    except Exception as e:
        print(f"Failed to initialize Chrome driver: {e}")
        return None

    wait = WebDriverWait(driver, 90)
    
    try:
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#username')))
        driver.execute_script(f'document.querySelector("#username").value = "{username}"')
        
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[name="action"]._button-login-id')))
        driver.execute_script('document.querySelector("button._button-login-id").click()')
        print("step 1 completed")
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#password')))
        driver.execute_script(f'document.querySelector("#password").value = "{password}"')
        
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[name="action"]._button-login-password')))
        driver.execute_script('document.querySelector("button._button-login-password").click()')
        print("login completed")
        return driver
    except Exception as e:
        print(f"Login failed: {e}")
        driver.quit()
        return None

def download_data(driver, link):
    if not driver:
        return None
        
    try:
        driver.get(link)
        wait = WebDriverWait(driver, 90)
        
        # -----------------------------------------------------------------
        # NEW SEQUENTIAL LOGIC
        # -----------------------------------------------------------------
        
        print("Attempting to click buttons in sequence...")
        
        # STEP 1: Click the Time-filter button
        time_filter_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="lookback-filter-section"]/div[2]/button')
        ))
        time_filter_button.click()
        print("✅ Step 1: Clicked 'Time-filter' button.")

        # STEP 2: Click the Time-filter-month button
        month_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="radix-:r6:"]/div/div[1]/button[2]')
        ))
        month_button.click()
        print("✅ Step 2: Clicked 'Time-filter-month' button.")

        # STEP 3: Click the Time-filter-confirm button
        confirm_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="radix-:r6:"]/div/div[2]/div[2]/button[2]')
        ))
        confirm_button.click()
        print("✅ Step 3: Clicked 'Time-filter-confirm' button.")
        
        # Give the page a moment to update after confirming filters
        time.sleep(2) 

        # STEP 4: Click the actual Excel Download button
        download_button = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, 'button[data-qa-id="excel-export-button"]')
        ))
        print("✅ Step 4: Found 'Excel export' button.")
        
        # -----------------------------------------------------------------
        # END OF NEW LOGIC
        # -----------------------------------------------------------------

        # Now, proceed with the download
        files_before = set(os.listdir("/tmp"))
        download_button.click()
        print("Download button clicked. Waiting for file...")
        
        downloaded_file = wait_for_download_complete("/tmp", files_before, timeout=120)
        print(f"File downloaded: {downloaded_file}")
        return downloaded_file
            
    except TimeoutException as e:
        print(f"🛑 ERROR: An element was not found or clickable in time.")
        print(f"Details: {e}")
        driver.save_screenshot("/tmp/error_screenshot.png") # Save screenshot for debugging
        print("Saved screenshot to /tmp/error_screenshot.png")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in download_data: {e}")
        return None
    finally:
        if driver:
            driver.quit()
            print("Driver quit.")
            
    return None # Explicitly return None if something went wrong before the end

def wait_for_download_complete(directory, files_before, timeout=120):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        files_after = set(os.listdir(directory))
        new_files = files_after - files_before
        
        if new_files:
            latest_file = max([os.path.join(directory, f) for f in new_files], key=os.path.getmtime)
            
            # Wait until the file is fully downloaded (not a temp file)
            if not latest_file.endswith('.crdownload'):
                return latest_file
                
        time.sleep(1)
    
    raise Exception(f"File did not download completely within {timeout} seconds.")
    
def sync_to_gsheet(xlsx_path, gsheet_id, sheet_title):
    service_account_file = "/tmp/service_account_key.json"
    
    # Check for service account key
    gcp_creds = os.getenv("GCP_SA_KEY")
    if gcp_creds:
        try:
            with open(service_account_file, 'w') as f:
                f.write(gcp_creds)
            print("Service account key file created from environment variable.")
        except Exception as e:
            print(f"Failed to write service account key file: {e}")
            return
    elif not os.path.exists(service_account_file):
        print("Service account key file not found and GCP_SA_KEY env var is not set.")
        return

    try:
        df_new = pd.read_excel(xlsx_path)
        print(f"Read {len(df_new)} rows from Excel file.") # Check how many rows are read
        
        if df_new.empty:
            print("Downloaded file is empty. Aborting sync.")
            return

        gc = pygsheets.authorize(service_file=service_account_file)
        sh = gc.open_by_key(gsheet_id)
        wks = sh.worksheet_by_title(sheet_title)
        
        wks.clear()
        print("Google Sheet cleared.")
        wks.set_dataframe(df_new, (1,1), nan='')
        print("Data updated in Google Sheet.")
    except Exception as e:
        print(f"An error occurred during Google Sheet sync: {e}")

if __name__ == "__main__":
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    GSHEET_ID = "18w-aiOm31RvsWXtqR2ZwdFaIIG1GOCMh1aogH4LrCnM"
    GSHEET_TITLE = "1-Month-Back Data"
    
    if not all([USERNAME, PASSWORD]):
        print("Username or Password environment variables not set.")
    else:
        # Note: The login function now handles creating the driver
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        
        # Only proceed if login was successful
        if driver:
            # The download_data function will quit the driver it receives
            downloaded_file_path = download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
            
            if downloaded_file_path:
                print(f"File to be synced: {downloaded_file_path}")
                sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)
            else:
                print("Download failed, skipping sync to Google Sheets.")
        else:
            print("Login failed, skipping download and sync.")
