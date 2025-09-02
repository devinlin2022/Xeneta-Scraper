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

def login(link, username, password):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    options.add_argument('--user-data-dir=/tmp/user-data-' + str(int(time.time())))
    
    download_dir = "/content"
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
        return
        
    try:
        driver.get(link)
        driver.implicitly_wait(20)
        print(f"Navigated to data page: {link}")
        
        wait = WebDriverWait(driver, 30)
        wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]')))
        
        element = driver.find_element(By.XPATH, '//*[@id="root"]/div/div[1]/div/header/div[2]/div/button[1]')
        driver.execute_script("arguments[0].click();", element)
        print("Element clicked successfully!")
    except Exception as e:
        print(f"An error occurred during data download: {e}")
    
    time.sleep(10)

if __name__ == "__main__":
    # 从环境变量中读取用户名和密码，而不是硬编码
    USERNAME = os.getenv("XENETA_USERNAME")
    PASSWORD = os.getenv("XENETA_PASSWORD")
    
    if not USERNAME or not PASSWORD:
        print("Username or password not found in environment variables. Please set XENETA_USERNAME and XENETA_PASSWORD.")
    else:
        driver = login("https://auth.xeneta.com/login", USERNAME, PASSWORD)
        
        download_data(driver, "https://app.xeneta.com/ocean/analyze/rate")
        
        if driver:
            driver.quit()
            print("WebDriver session closed.")
