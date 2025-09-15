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
@@ -63,36 +67,111 @@ def login(link, username, password):
def download_data(driver, link):
    if not driver:
        print("No valid WebDriver instance to proceed with download.")
        return
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

    time.sleep(10)
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
        print("Data upload successfully!")
