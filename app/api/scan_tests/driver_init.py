from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time, os



def driver_init():

    prefs = {
        'download.prompt_for_download': False,
        'download.extensions_to_open': '.zip',
        'safebrowsing.enabled': True
    }
    chrome_path = os.environ.get('CHROMEDRIVER')
    WINDOW_SIZE = "1920,1080"
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs',prefs)
    options.add_argument("start-maximized")
    options.add_argument("--headless")
    options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'})
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=%s" % WINDOW_SIZE)
    options.add_argument("--safebrowsing-disable-download-protection")
    options.add_argument("safebrowsing-disable-extension-blacklist")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(executable_path=chrome_path, options=options)
    driver.set_page_load_timeout(20)
    driver.set_script_timeout(20)
    driver.implicitly_wait(20)

    
    return driver