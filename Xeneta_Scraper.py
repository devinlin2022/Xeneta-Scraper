import os
import time
import pandas as pd
import pygsheets
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 统一配置区域 ---
# 1. 临时文件和路径配置
TEMP_DIR = "/tmp"  # 统一指定临时文件夹
SERVICE_ACCOUNT_FILENAME = "service_account_key.json" # 服务账户密钥文件名
SERVICE_ACCOUNT_FILE_PATH = os.path.join(TEMP_DIR, SERVICE_ACCOUNT_FILENAME) # 密钥的完整路径
SCREENSHOT_PATH = os.path.join(TEMP_DIR, "debug_screenshot.png") # 失败时截图的保存路径

# 2. Google Sheets 配置
GSHEET_ID = "1WUBSE7UD_GrD-LziCZKUJrbC4EhqY2MmU6HA7VLJL-A"
GSHEET_TITLE = "Data"

# 3. Xeneta 网站链接
XENETA_LOGIN_URL = "https://auth.xeneta.com/login"
XENETA_DATA_URL = "https://app.xeneta.com/ocean/analyze/rate"


def login(username, password):
    """使用Selenium登录Xeneta"""
    print("开始配置Chrome浏览器...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # 为浏览器用户数据也使用临时文件夹，避免权限问题
    options.add_argument(f'--user-data-dir={os.path.join(TEMP_DIR, "chrome-user-data")}')
    
    # 确保下载目录存在
    os.makedirs(TEMP_DIR, exist_ok=True)
        
    prefs = {
        "download.default_directory": TEMP_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option('prefs', prefs)
    
    driver = None # 先初始化driver为None
    try:
        driver = webdriver.Chrome(options=options)
        print(f"浏览器初始化成功，正在打开登录页面: {XENETA_LOGIN_URL}")
        driver.get(XENETA_LOGIN_URL)
        
        # 使用更长的等待时间，增加稳定性
        wait = WebDriverWait(driver, 60)
        
        print("输入用户名...")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#username')))
        driver.execute_script(f'document.querySelector("#username").value = "{username}"')
        
        print("点击下一步...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
        driver.execute_script('document.querySelector(\'button[type="submit"]\').click()')
        
        print("输入密码...")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#password')))
        driver.execute_script(f'document.querySelector("#password").value = "{password}"')
        
        print("点击登录...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
        driver.execute_script('document.querySelector(\'button[type="submit"]\').click()')

        # 等待登录成功后某个特定元素出现，以确认登录成功
        # 这里以页面上的某个通用元素为例，您可能需要换成更可靠的元素
        wait.until(EC.presence_of_element_located((By.ID, "root")))
        print("登录成功！")
        return driver

    except Exception as e:
        print(f"登录过程中发生错误: {e}")
        if driver:
            print(f"错误发生，截取屏幕快照并保存至: {SCREENSHOT_PATH}")
            driver.save_screenshot(SCREENSHOT_PATH)
            driver.quit()
        return None

def wait_for_download_complete(directory, timeout=120):
    """
    等待下载完成的函数，逻辑更健壮。
    它会监控目录，直到找到一个新的 .xlsx 文件并且没有 .crdownload 文件。
    """
    start_time = time.time()
    files_before = set(os.listdir(directory))
    
    while time.time() - start_time < timeout:
        files_after = set(os.listdir(directory))
        new_files = files_after - files_before
        
        # 如果有新文件
        if new_files:
            # 检查是否有 .crdownload 文件，这是Chrome下载时的临时文件
            crdownload_files = [f for f in new_files if f.endswith('.crdownload')]
            
            # 如果没有 .crdownload 文件了，说明下载可能已完成
            if not crdownload_files:
                xlsx_files = [f for f in new_files if f.endswith('.xlsx')]
                if xlsx_files:
                    # 获取最新的xlsx文件
                    latest_file = max(xlsx_files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
                    file_path = os.path.join(directory, latest_file)
                    print(f"下载完成，文件已找到: {file_path}")
                    return file_path
        
        time.sleep(1) # 每秒检查一次
    
    print(f"错误: 在 {timeout} 秒内未检测到完整的下载文件。")
    return None

def download_data(driver):
    """导航到数据页面并下载Excel文件"""
    if not driver:
        print("浏览器驱动无效，跳过下载步骤。")
        return None
    
    try:
        print(f"正在导航到数据页面: {XENETA_DATA_URL}")
        driver.get(XENETA_DATA_URL)
        
        wait = WebDriverWait(driver, 60)
        
        print("等待下载按钮加载...")
        # 使用更稳定的选择器，例如基于按钮的文本或功能属性
        download_button_xpath = "//button[contains(., 'Download') or contains(., 'Export')]"
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, download_button_xpath)))
        
        print("找到下载按钮，准备点击...")
        download_button.click()
        print("已点击下载按钮，现在等待文件下载完成...")
        
        # 调用健壮的等待下载函数
        downloaded_file = wait_for_download_complete(TEMP_DIR, timeout=180)
        return downloaded_file
        
    except Exception as e:
        print(f"下载数据时发生错误: {e}")
        print(f"错误发生，截取屏幕快照并保存至: {SCREENSHOT_PATH}")
        driver.save_screenshot(SCREENSHOT_PATH)
        return None
    finally:
        if driver:
            print("关闭浏览器。")
            driver.quit()

def sync_to_gsheet(xlsx_path):
    """将Excel文件同步到Google Sheets"""
    print(f"开始同步文件 '{xlsx_path}' 到 Google Sheets...")
    
    if not os.path.exists(SERVICE_ACCOUNT_FILE_PATH):
        print(f"错误: Service Account Key 文件未找到于路径: {SERVICE_ACCOUNT_FILE_PATH}")
        return

    try:
        print("正在读取下载的Excel文件...")
        df_new = pd.read_excel(xlsx_path)
        
        print("正在授权 Google Sheets API...")
        gc = pygsheets.authorize(service_file=SERVICE_ACCOUNT_FILE_PATH)
        
        print(f"正在打开工作簿 (ID: {GSHEET_ID})...")
        sh = gc.open_by_key(GSHEET_ID)
        
        print(f"正在选择工作表: '{GSHEET_TITLE}'...")
        wks = sh.worksheet_by_title(GSHEET_TITLE)
        
        print("清除旧数据...")
        wks.clear()
        
        print("正在上传新数据...")
        wks.set_dataframe(df_new, (1, 1), nan='')
        print("数据上传成功！同步完成。")
        
    except Exception as e:
        print(f"同步到 Google Sheets 时发生错误: {e}")

if __name__ == "__main__":
    print("--- Xeneta Scraper 任务开始 ---")
    
    # 从环境变量中获取机密信息
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    if not USERNAME or not PASSWORD:
        print("错误: 必须在GitHub Secrets中设置 XENETA_USERNAME 和 XENETA_PASSWORD")
    else:
        driver = login(USERNAME, PASSWORD)
        
        if driver:
            downloaded_file_path = download_data(driver)
            
            if downloaded_file_path:
                sync_to_gsheet(downloaded_file_path)
            else:
                print("下载失败，无法进行同步。")
        else:
            print("登录失败，任务终止。")
            
    print("--- Xeneta Scraper 任务结束 ---")
