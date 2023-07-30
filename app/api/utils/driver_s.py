from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver import ActionChains
import time, os, numpy, json, sys



def driver_init(
    window_size='1920,1080', 
    device='desktop',
    script_timeout=30,
    load_timeout=30,
    wait_time=15, 
    ):

    sizes = window_size.split(',')

    prefs = {
        'download.prompt_for_download': False,
        'download.extensions_to_open': '.zip',
        'safebrowsing.enabled': True
    }

    mobile_emulation = {
        "deviceMetrics": { "width": int(sizes[0]), "height": int(sizes[1]), "pixelRatio": 1.0 },
        "userAgent": (
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/99.0.4844.74 Mobile Safari/537.36"
        ) 
    }

    chromedriver_path = os.environ.get("CHROMEDRIVER")
    options = webdriver.ChromeOptions()
    options.binary_location = os.environ.get('CHROMIUM')
    options.add_argument("--no-sandbox")
    options.add_argument("disable-blink-features=AutomationControlled")
    options.add_experimental_option('prefs',prefs)
    options.add_argument("start-maximized")
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--force-device-scale-factor=0.5")
    options.add_argument("--window-size=%s" % window_size) 

    if device == 'mobile':
        options.add_experimental_option("mobileEmulation", mobile_emulation)

    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}

    driver = webdriver.Chrome(executable_path=chromedriver_path, options=options, desired_capabilities=caps)
    driver.set_page_load_timeout(load_timeout)
    driver.set_script_timeout(script_timeout)
    driver.implicitly_wait(wait_time)

    
    return driver


def driver_test():
    
    print("Testing selenium instalation and integration...")
    try:
        driver = driver_init()
        driver.get('https://google.com')
        title = driver.title
        assert title == 'Google'
        if title == 'Google':
            status = 'Success'
        else:
            status = 'Failed'
    except Exception as e:
        print(e)
        status = 'Failed'

    sys.stdout.write('--- ' + status + ' ---\n'
        + 'Selenium installed and working \N{check mark} \n'
        )

    quit_driver(driver)
    sys.exit(0)



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
        # simulate mouse movement and click on <html> tag
        html_tag = driver.find_elements_by_tag_name('html')[0]
        action = ActionChains(driver)
        action.move_to_element(html_tag).perform()
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




def quit_driver(driver):
    ''' 
    Quits and reaps all child processes in docker
    '''
    print('Quitting session: %s' % driver.session_id)
    driver.quit()
    try:
        pid = True
        while pid:
            pid = os.waitpid(-1, os.WNOHANG)
            print("Reaped child: %s" % str(pid))

            # avoid infinite loop cause pid value -> (0, 0)
            try:
                if pid[0] == 0:
                    pid = False
            except:
                pass


    except ChildProcessError:
        pass