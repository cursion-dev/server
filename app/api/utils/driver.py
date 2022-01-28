from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver import ActionChains
import time, os, numpy, json



def driver_init():

    prefs = {
        'download.prompt_for_download': False,
        'download.extensions_to_open': '.zip',
        'safebrowsing.enabled': True
    }
    chrome_path = os.environ.get("CHROMEDRIVER")
    WINDOW_SIZE = "1920,1080"
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs',prefs)
    options.add_argument("start-maximized")
    options.add_argument("--headless")
    options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'})
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=%s" % WINDOW_SIZE)
    options.add_argument("--safebrowsing-disable-download-protection")
    options.add_argument("safebrowsing-disable-extension-blacklist")
    options.add_argument("--disable-gpu")

    caps = DesiredCapabilities.CHROME
    #as per latest docs
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}

    driver = webdriver.Chrome(executable_path=chrome_path, options=options, desired_capabilities=caps)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    driver.implicitly_wait(60)

    
    return driver




def driver_wait(driver, interval=5, max_wait_time=30, min_wait_time=5):
    """
    Pauses the driver until all network requests have been resolved

    --> Adding mouse interaction to load WP plugin rendered content

    returns once driver determines that all request have resolved or 
    total wait time exceeds max_wait_time <int>
    
    """

    def get_request_list(driver):
        # get current snapshot of driver requests 
        requests = driver.get_log('performance')
        r_list = []
        for r in requests:
            network_log = json.loads(r["message"])["message"]

            # Checks if the current 'method' key has any Network related value.
            if("Network.response" in network_log["method"]
                or "Network.request" in network_log["method"]
                or "Network.webSocket" in network_log["method"]):

                r_list.append(network_log)

        return r_list


    def interact_with_page(driver):
        # simulate mouse movement and click on <body> tag
        body_tag = driver.find_elements_by_tag_name('body')[0]
        action = ActionChains(driver)
        action.move_to_element(body_tag).click().perform()
        return


    resolved = False
    wait_time = 0

    # actions before comparing network logs
    interact_with_page(driver)
    time.sleep(min_wait_time)

    while not resolved and wait_time < max_wait_time:
        # get first set of logs
        list_one = get_request_list(driver=driver)
        
        # wait 5 sec or <interval:int> sec for request to resolve
        time.sleep(interval)
        
        # get second set of logs
        list_two = get_request_list(driver=driver)
        
        # check if logs are equal
        resolved = numpy.array_equal(list_one, list_two)
        
        wait_time += interval

    return