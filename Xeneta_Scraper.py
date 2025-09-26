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
        "safebrowsing.enabled": True
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
        
        download_button = None
        
        # Define a list of locators to try in order
        locators = [
            {"method": By.XPATH, "value": '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]', "name": "Original XPath"},
            {"method": By.CSS_SELECTOR, "value": 'button[data-qa-id="excel-export-button"]', "name": "CSS Selector (data-qa-id)"},
            {"method": By.XPATH, "value": "//button[contains(., 'Excel')]", "name": "XPath (text contains 'Excel')"}
        ]

        # Loop through the locators and try to find the button
        for locator in locators:
            try:
                print(f"Attempting to find download button by: {locator['name']}...")
                download_button = wait.until(EC.element_to_be_clickable((locator["method"], locator["value"])))
                print("✅ Button found!")
                break  # Exit the loop if the button is found
            except Exception:
                print(f"❌ Could not find button using {locator['name']}. Trying next method...")

        # If the button was found, click it and proceed
        if download_button:
            files_before = set(os.listdir("/tmp"))
            download_button.click()
            print("Download button clicked.")
            
            # The original logic for waiting for an element to disappear
            radix_element_id = "#radix-\\:rf1\\:"
            try:
                # Use a shorter wait here if this element is not always present
                short_wait = WebDriverWait(driver, 5)
                short_wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, radix_element_id)))
            except Exception:
                pass # It's okay if this element doesn't appear
            
            downloaded_file = wait_for_download_complete("/tmp", files_before, timeout=120)
            print(f"File downloaded: {downloaded_file}")
            return downloaded_file
        else:
            print("🛑 ERROR: Could not find the download button using any method. Aborting download.")
            return None
            
    except Exception as e:
        print(f"An unexpected error occurred in download_data: {e}")
        return None
    finally:
        if driver:
            driver.quit()
            
    return None

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
    if not os.path.exists(service_account_file):
        print("Service account key file not found.")
        return

    try:
        df_new = pd.read_excel(xlsx_path)
        print("Read new data from Excel file.")
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
    GSHEET_TITLE = "Data"
    
    if not all([USERNAME, PASSWORD]):
        print("Username or Password environment variables not set.")
    else:
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        
        # Only proceed if login was successful
        if driver:
            downloaded_file_path = download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
            if downloaded_file_path:
                print(f"File to be synced: {downloaded_file_path}")
                sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)
            else:
                print("Download failed, skipping sync to Google Sheets.")
