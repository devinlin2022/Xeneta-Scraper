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
        
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'body > div.widget > main > section > div > div > div > div > div > form > div.ca17d988b > button')))
        driver.execute_script(f'document.querySelector("body > div.widget > main > section > div > div > div > div > div > form > div.ca17d988b > button").click()')
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#password')))
        driver.execute_script(f'document.querySelector("#password").value = "{password}"')
        
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'body > div.widget > main > section > div > div > div > form > div.ca17d988b > button')))
        driver.execute_script(f'document.querySelector("body > div.widget > main > section > div > div > div > form > div.ca17d988b > button").click()')
        
        return driver
    except Exception as e:
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
    # --- 开始修改 ---
    print(f"开始同步文件 '{xlsx_path}' 到 Google Sheet '{sheet_title}'...") # 增加日志，确认函数被调用
    
    service_account_file = "/tmp/service_account_key.json"
    
    # 增加检查，确认密钥文件是否存在
    if not os.path.exists(service_account_file):
        print(f"错误：Service account 密钥文件未在 '{service_account_file}' 找到！")
        return

    # 增加检查，确认下载的 excel 文件是否存在
    if not os.path.exists(xlsx_path):
        print(f"错误：下载的 Excel 文件 '{xlsx_path}' 不存在！无法上传。")
        return

    try:
        df_new = pd.read_excel(xlsx_path)
        print("Excel 文件读取成功。")
        
        gc = pygsheets.authorize(service_file=service_account_file)
        print("Google API 授权成功。")
        
        sh = gc.open_by_key(gsheet_id)
        print(f"成功打开工作簿 (Spreadsheet)。")
        
        wks = sh.worksheet_by_title(sheet_title)
        print(f"成功定位到工作表 (Worksheet): '{sheet_title}'。")
        
        wks.clear()
        print("工作表已清空。")
        
        wks.set_dataframe(df_new, (1,1), nan='')
        print("✅ 数据成功写入 Google Sheet！")

    except Exception as e:
        print(f"!!!!!! 上传到 Google Sheet 失败 !!!!!!")
        print(f"具体的错误信息是: {e}")
        # 如果需要更详细的堆栈信息用于调试，可以取消下面这行的注释
        # import traceback
        # traceback.print_exc()
    # --- 结束修改 ---

if __name__ == "__main__":
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    GSHEET_ID = "1WUBSE7UD_GrD-LziCZKUJrbC4EhqY2MmU6HA7VLJL-A"
    GSHEET_TITLE = "Data"
    
    if not all([USERNAME, PASSWORD]):
        # 您的原始逻辑
        pass 
    else:
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        downloaded_file_path = download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
        sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)

