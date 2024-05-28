from selenium import webdriver
from selenium.webdriver.common.actions.action_builder import ActionBuilder
import time, os, sys






def driver_init(
        window_size: str='1920,1080', 
        device: str='desktop',
        script_timeout: int=30,
        load_timeout: int=30,
        wait_time: int=15, 
        pixel_ratio: int=1.0,
        scale_factor: int=0.5
    ) -> object:
    """ 
    Starts a new selenium driver instance

    Expects: {
        'window_size'   : str, 
        'device'        : str,
        'script_timeout': int,
        'load_timeout'  : int,
        'wait_time'     : int, 
        'pixel_ratio'   : int,
        'scale_factor'  : int
    } 

    Returns -> driver object
    """

    # setting up browser configs
    sizes = window_size.split(',')
    prefs = {
        'download.prompt_for_download': False,
        'download.extensions_to_open': '.zip',
        'safebrowsing.enabled': True
    }
    mobile_emulation = {
        "deviceMetrics": { 
            "width": int(sizes[0]), 
            "height": int(sizes[1]), 
            "pixelRatio": pixel_ratio 
        },
        "userAgent": (
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36"
        ) 
    }

    # setting browser options
    options = webdriver.ChromeOptions()
    options.binary_location = os.environ.get('CHROME_BROWSER')
    options.add_argument("--no-sandbox")
    options.add_argument("disable-blink-features=AutomationControlled")
    options.add_experimental_option('prefs',prefs)
    options.add_argument("start-maximized")
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("ignore-certificate-errors")
    options.add_argument("--hide-scrollbars")
    options.add_argument(f"--force-device-scale-factor={str(scale_factor)}")
    options.add_argument(f"--window-size={window_size}") 
    options.set_capability("goog:loggingPrefs", {'performance': 'ALL'})
    options.page_load_strategy = 'none'

    # setting to mobile if reqeusted
    if device == 'mobile':
        options.add_experimental_option("mobileEmulation", mobile_emulation)

    # chromedriver_path = os.environ.get("CHROMEDRIVER")
    # service = webdriver.ChromeService(executable_path=chromedriver_path)
    driver = webdriver.Chrome(options=options)
    # driver.set_page_load_timeout(load_timeout)
    # driver.set_script_timeout(script_timeout)
    # driver.implicitly_wait(wait_time)

    return driver




def driver_test() -> None:
    """ 
    Spins up a selenium driver instance and
    tests to ensure it can access the browser and internet

    Returns -> None
    """
    
    print("Testing selenium instalation and integration...")
    message = 'Selenium was unable to start\n\n'
    status = 'Failed'
    
    # testing selenium
    try:
        driver = driver_init()
        driver.get('https://google.com')
        title = driver.title
        assert title == 'Google'
        if title == 'Google':
            status = 'Success'
            message = 'Selenium installed and working \N{check mark} \n\n'
    # log exception   
    except Exception as e:
        print(e)
    
    # logging test results
    sys.stdout.write(
        '--- ' + status + ' ---\n'+ message
    )
    
    try:
        quit_driver(driver)
        sys.exit(0)
    except:
        pass
    
    return None




def driver_wait(
        driver: object, 
        interval: int=1, 
        max_wait_time: int=30, 
        min_wait_time: int=3
    ) -> object:
    """
    Expects the driver instance and waits 
    for either the page to fully load or the max_wait_time
    to expire before returning.

    Expects: {
        'driver'        : object, 
        'interval'      : int,
        'max_wait_time' : int,
        'min_wait_time' : int
    }

    Returns -> driver object
    """

    def interact_with_page(driver):
        # simulate mouse movement
        action = ActionBuilder(driver)
        action.pointer_action.move_to_location(0, 0)
        action.perform()
        # wait for 1s
        time.sleep(1)
        action.pointer_action.move_to_location(0, 50)
        action.perform()
        return


    resolved = False
    page_state = 'loading'
    wait_time = 0

    # min_wait_time before checking page status
    time.sleep(min_wait_time)

    while int(wait_time) < int(max_wait_time) and page_state != 'complete':
        # wait 1 sec or <interval:int> sec 
        time.sleep(interval)

        page_state = driver.execute_script('return document.readyState')
        print(f'document state is {page_state}')
        
        wait_time += interval
    
    # interacting with page once available
    interact_with_page(driver)

    return None




def get_data(
        driver: object, 
        interval: int=1, 
        max_wait_time: int=30, 
        min_wait_time: int=3
    ) -> dict:
    """
    Once the page has loaded, grabs the
    page-source (html) and console-logs (logs).

    Expects: {
        'driver'        : object, 
        'interval'      : int,
        'max_wait_time' : int,
        'min_wait_time' : int
    }

    Returns -> data = {
        'html' : str,
        'logs' : dict
    }
    """

    # setting defaults
    html = None
    logs = None

    # waiting for page to load
    driver_wait(driver=driver)

    # get data from browser
    try:
        html = driver.page_source
        logs = driver.get_log('browser')
    except Exception as e:
        print(e)

    # formatting respones
    data = {
        "html": html,
        "logs": logs
    }

    return data




def quit_driver(driver: object) -> None:
    """ 
    Quits and reaps all child processes in docker

    Returns -> None
    """
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



    