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
        return None

    wait = WebDriverWait(driver, 30)
    
    try:
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#username')))
        driver.execute_script(f'document.querySelector("#username").value = "{username}"')
        
        # wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'body > div.widget > main > section > div > div > div > div > div > form > div.cdebb54bf > button')))
        # driver.execute_script(f'document.querySelector("body > div.widget > main > section > div > div > div > div > div > form > div.cdebb54bf > button").click()')
        continue_button_1 = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]._button-login-id')))
        continue_button_1.click()
        print("step 1 completed")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#password')))
        driver.execute_script(f'document.querySelector("#password").value = "{password}"')
        
        # wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'body > div.widget > main > section > div > div > div > form > div.cdebb54bf > button')))
        # driver.execute_script(f'document.querySelector("body > div.widget > main > section > div > div > div > form > div.cdebb54bf > button").click()')
        continue_button_2 = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]._button-login-password')))
        continue_button_2.click()
        print("login completed")
        return driver
    except Exception as e:
        print("login failed")
        driver.quit()
        return None

def download_data(driver, link):
    if not driver:
        return None
        
    try:
        driver.get(link)
        driver.implicitly_wait(20)
        
        wait = WebDriverWait(driver, 30)
        
        files_before = set(os.listdir("/tmp"))
        
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]')))
        download_button.click()
        
        radix_element_id = "#radix-\\:rf1\\:"
        try:
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, radix_element_id)))
        except:
            pass
        
        downloaded_file = wait_for_download_complete("/tmp", files_before, timeout=120)
        print(downloaded_file)
        return downloaded_file
        
    except Exception as e:
        pass
    finally:
        if driver:
            driver.quit()
        
    return None

def wait_for_download_complete(directory, files_before, timeout=60):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        files_after = set(os.listdir(directory))
        new_files = files_after - files_before
        
        if new_files:
            latest_file = max([os.path.join(directory, f) for f in new_files], key=os.path.getmtime)
            
            if latest_file.endswith('.crdownload') or not latest_file.endswith('.xlsx'):
                pass
            else:
                return latest_file
                
        time.sleep(1)
    
    files_after_timeout = set(os.listdir(directory))
    new_files_at_timeout = files_after_timeout - files_before

    if new_files_at_timeout:
        pass
    
    raise Exception(f"File did not download within {timeout} seconds.")
    
def sync_to_gsheet(xlsx_path, gsheet_id, sheet_title):
    service_account_file = "/tmp/service_account_key.json"
    if not os.path.exists(service_account_file):
        print("services account no exist")
        return

    try:
        df_new = pd.read_excel(xlsx_path)
        print(df_new.head())
        gc = pygsheets.authorize(service_file=service_account_file)
        sh = gc.open_by_key(gsheet_id)
        wks = sh.worksheet_by_title(sheet_title)
        
        wks.clear()
        print("data cleaned")
        wks.set_dataframe(df_new, (1,1), nan='')
        print("data updated")
    except Exception as e:
        pass

if __name__ == "__main__":
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    GSHEET_ID = "1WUBSE7UD_GrD-LziCZKUJrbC4EhqY2MmU6HA7VLJL-A"
    GSHEET_TITLE = "Data"
    
    if not all([USERNAME, PASSWORD]):
        pass
    else:
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        
        downloaded_file_path = download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
        print(downloaded_file_path)
        sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)

