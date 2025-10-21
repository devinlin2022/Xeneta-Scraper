import os
import pandas as pd
import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta  # 导入这个库来计算日期
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pygsheets
import json

def login(link, username, password):
    # (这个函数保持不变，和你的原版一样)
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
    # (这个函数被修改了)
    if not driver:
        return None
        
    try:
        # driver.get(link) 是在主程序中计算好日期的 URL
        driver.get(link) 
        wait = WebDriverWait(driver, 90)
        
        download_button = None
        
        # *** 修改点 ***
        # 我们不再需要点击筛选按钮，所以只保留下载按钮的定位器
        locators = [
            {"method": By.CSS_SELECTOR, "value": 'button[data-qa-id="excel-export-button"]', "name": "CSS Selector (data-qa-id)"},
            {"method": By.XPATH, "value": '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]', "name": "Original XPath"},
            {"method": By.XPATH, "value": "//button[contains(., 'Excel')]", "name": "XPath (text contains 'Excel')"}
        ]

        # 循环尝试找到 *下载* 按钮
        for locator in locators:
            try:
                print(f"Attempting to find download button by: {locator['name']}...")
                download_button = wait.until(EC.element_to_be_clickable((locator["method"], locator["value"])))
                print("✅ Download button found!")
                break  # 找到了就跳出循环
            except Exception:
                print(f"❌ Could not find button using {locator['name']}. Trying next method...")

        # 如果找到了下载按钮，就点击它
        if download_button:
            files_before = set(os.listdir("/tmp"))
            download_button.click()
            print("Download button clicked.")
            
            # (你原来的等待逻辑，保留)
            radix_element_id = "#radix-\\:rf1\\:"
            try:
                short_wait = WebDriverWait(driver, 5)
                short_wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, radix_element_id)))
            except Exception:
                pass 
            
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
    # (这个函数保持不变，和你的原版一样)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        files_after = set(os.listdir(directory))
        new_files = files_after - files_before
        
        if new_files:
            latest_file = max([os.path.join(directory, f) for f in new_files], key=os.path.getmtime)
            
            if not latest_file.endswith('.crdownload'):
                return latest_file
                
        time.sleep(1)
    
    raise Exception(f"File did not download completely within {timeout} seconds.")
    
def sync_to_gsheet(xlsx_path, gsheet_id, sheet_title):
    # (这个函数保持不变，和你的原版一样)
    # (请确保你的 GitHub Actions secrets 里配置了 GCP_SA_KEY)
    service_account_file = "/tmp/service_account_key.json"
    
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
        print(f"Read {len(df_new)} rows from Excel file.")
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
    # (这个函数被修改了)
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    GSHEET_ID = "18w-aiOm31RvsWXtqR2ZwdFaIIG1GOCMh1aogH4LrCnM"
    GSHEET_TITLE = "1-Month-Back Data"
    
    if not all([USERNAME, PASSWORD]):
        print("Username or Password environment variables not set.")
    else:
        # *** 新增逻辑：计算日期并构建 URL ***
        try:
            # 1. 计算日期
            today = datetime.now()
            one_month_ago = today - relativedelta(months=1)
            formatted_date = one_month_ago.strftime("%Y-%m-%d") # 格式化为 YYYY-MM-DD
            print(f"Today is: {today.strftime('%Y-%m-%d')}. Target date (1 month ago): {formatted_date}")

            # 2. 构建包含所有参数的 URL
            base_url = "https://app.xeneta.com/ocean/analyze/rate"
            params = (
                f"?market_metric=mean"
                f"&market_filter_length=short"
                f"&company_filter_length=all"
                f"&lookback_day={formatted_date}"  # 使用我们计算的日期
                f"&thc_meth=user"
                f"&bump_level_max=100"
                f"&selectedTable=all"
            )
            target_url = base_url + params
            print(f"Constructed URL: {target_url}")

            # 3. 登录
            driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
            
            if driver:
                # 4. 传入 *包含日期的新 URL* 来下载数据
                downloaded_file_path = download_data(driver, target_url) 
                
                if downloaded_file_path:
                    print(f"File to be synced: {downloaded_file_path}")
                    sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)
                else:
                    print("Download failed, skipping sync to Google Sheets.")
            else:
                print("Login failed, skipping download and sync.")
                
        except Exception as e:
            print(f"An error occurred in the main process: {e}")
