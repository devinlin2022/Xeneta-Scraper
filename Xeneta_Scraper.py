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
import base64
import json

def login(link, username, password):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-data-dir=/tmp/user-data-' + str(int(time.time())))
    
    download_dir = "/content"
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
        print("WebDriver session successfully created.")
        driver.implicitly_wait(10)
        driver.get(link)
        print(f"Navigated to login page: {link}")
    except Exception as e:
        print(f"Error creating WebDriver session or navigating: {e}")
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
        
        print('Log in successful!')
        return driver
    except Exception as e:
        print(f"Login failed: {e}")
        driver.quit()
        return None

def download_data(driver, link):
    if not driver:
        print("No valid WebDriver instance to proceed with download.")
        return None
        
    try:
        driver.get(link)
        driver.implicitly_wait(20)
        print(f"Navigated to data page: {link}")
        
        wait = WebDriverWait(driver, 30)
        
        # 等待下载按钮可见并可点击
        wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]')))
        
        element = driver.find_element(By.XPATH, '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]')
        driver.execute_script("arguments[0].click();", element)
        print("Element clicked successfully!")
        
        # 使用更可靠的函数来等待下载结束
        downloaded_file = wait_for_download_complete("/content", timeout=120)
        return downloaded_file
        
    except Exception as e:
        print(f"An error occurred during data download: {e}")
    finally:
        print("任务完成，关闭浏览器。")
        driver.quit()
        
    return None

def wait_for_download_complete(directory, timeout=60):
    """
    等待下载完成的辅助函数。
    它会检查下载目录，直到不再有 .crdownload (Chrome临时下载文件) 文件为止。
    """
    start_time = time.time()
    print("正在等待文件下载完成...")
    while time.time() - start_time < timeout:
        # 检查目录中是否有任何以 .crdownload 结尾的文件
        if not any(file.endswith('.crdownload') for file in os.listdir(directory)):
            # 找到最新的一个.xlsx文件作为下载成功的文件
            xlsx_files = [f for f in os.listdir(directory) if f.startswith('rate_all_') and f.endswith('.xlsx')]
            if xlsx_files:
                latest_file = max([os.path.join(directory, f) for f in xlsx_files], key=os.path.getmtime)
                print(f"文件下载成功: {latest_file}")
                return latest_file
        time.sleep(1) # 每隔1秒检查一次
    raise Exception(f"错误：文件在 {timeout} 秒内未下载完成。")
    
def sync_to_gsheet(xlsx_path, gsheet_id, sheet_title):
    """将清理后的 XLSX 同步到 Google Sheet"""
    # 从环境变量中获取 Base64 编码的凭证
    creds_base64 = os.getenv("GOOGLE_SHEET_CREDENTIALS")
    if not creds_base64:
        print("Error: GOOGLE_SHEET_CREDENTIALS environment variable not set.")
        return

    # 解码凭证并保存到临时文件
    try:
        creds_json = base64.b64decode(creds_base64).decode('utf-8')
        service_account_file = "/tmp/service_account.json"
        with open(service_account_file, "w") as f:
            f.write(creds_json)
        print("Service account file created successfully.")
    except Exception as e:
        print(f"Error decoding or writing credentials: {e}")
        return

    try:
        df_new = pd.read_excel(xlsx_path)
        
        # 使用服务账户进行授权
        gc = pygsheets.authorize(service_file=service_account_file)
        sh = gc.open_by_key(gsheet_id)
        wks = sh.worksheet_by_title(sheet_title)
        
        print("成功连接到 Google Sheet。")

        try:
            df_old = wks.get_as_df(has_header=True, include_tailing_empty=False)
            df_all = pd.concat([df_old, df_new], ignore_index=True)
            df_all.drop_duplicates(inplace=True)
        except Exception:
            df_all = df_new
            
        wks.clear()
        wks.set_dataframe(df_all, (1,1), nan='')
        print("数据已成功同步到 Google Sheet 并完成去重。")
    except Exception as e:
        print(f"同步到 Google Sheet 时发生错误: {e}")

if __name__ == "__main__":
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    # 使用硬编码的 Google Sheet ID 和工作表名称
    GSHEET_ID = "1WUBSE7UD_GrD-LziCZKUJrbC4EhqY2MmU6HA7VLJL-A"
    GSHEET_TITLE = "Data"
    
    if not all([USERNAME, PASSWORD]):
        print("Error: One or more environment variables not set. Please set XENETA_USERNAME and XENETA_PASSWORD.")
    else:
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        
        downloaded_file_path = download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
        
        if downloaded_file_path:
            sync_to_gsheet(downloaded_file_path, GSHEET_ID, GSHEET_TITLE)
        else:
            print("Download failed, skipping Google Sheet sync.")
