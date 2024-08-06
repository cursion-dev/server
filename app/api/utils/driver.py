from selenium import webdriver
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from datetime import datetime
import time, os, sys






def driver_init(
        browser: str='chrome',
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
        'browser'       : str,
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

    # deciding on browser
    if browser == 'chrome':
        options = webdriver.ChromeOptions()
        options.binary_location = os.environ.get('CHROME_BROWSER')
        mobile_user_agent = (
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36" + 
            " (KHTML, like Gecko) Chrome/127.0.6533.84 Mobile Safari/537.36"
        )
    if browser == 'firefox':
        options = webdriver.FirefoxOptions()
        options.binary_location = os.environ.get('FIREFOX_BROWSER')
        mobile_user_agent = (
            "Mozilla/5.0 (Android 14; Mobile; rv:68.0) Gecko/68.0 Firefox/128.0"
        )

    # setting up browser configs
    sizes = window_size.split(',')
    width = int(sizes[0])
    height = int(sizes[1])
    mobile_emulation = {
        "deviceMetrics": { 
            "width": width, 
            "height": height,
            "pixelRatio": pixel_ratio 
        },
        "userAgent": mobile_user_agent
    }

    # setting broswer options for chrome
    if browser == 'chrome':
        options.add_argument("--no-sandbox")
        options.add_argument("disable-blink-features=AutomationControlled")
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("ignore-certificate-errors")
        options.add_argument("--hide-scrollbars")
        options.add_argument(f"--force-device-scale-factor={str(scale_factor)}")
        options.set_capability("goog:loggingPrefs", {'performance': 'ALL'})
        options.page_load_strategy = 'none'
        
        # setting to mobile if reqeusted
        if device == 'mobile':
            options.add_experimental_option("mobileEmulation", mobile_emulation)
        
        # init driver
        driver = webdriver.Chrome(options=options)
    
    # setting broswer options & profile for firefox
    if browser == 'firefox':
        options.add_argument("-headless")
        options.page_load_strategy = 'none'
        options.set_preference("accept_insecure_certs", True)
        options.set_preference('layout.css.devPixelsPerPx', str(scale_factor))

        # setting to mobile if reqeusted
        if device == 'mobile':
            options.set_preference(
                "general.useragent.override", f"userAgent={mobile_user_agent}"
            )
        
        # init driver
        driver = webdriver.Firefox(options=options)
    

    # resizing window
    driver.maximize_window()
    driver.set_window_size(width, height)
    print(f'Using {browser} browser')

    return driver




def driver_test() -> None:
    """ 
    Spins up a selenium driver instance and
    tests to ensure it can access the browser and internet

    Returns -> None
    """
    
    print("Testing Selenium...")
    message = 'Selenium was unable to start\n\n'
    status = 'Failed'
    
    # testing selenium
    try:
        driver = driver_init()
        driver.set_page_load_timeout(20)
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
    ) -> bool:
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

    Returns -> bool (True if page is loaded)
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

        # get current timestamp
        pre_check_time = datetime.now()
        
        # wait 1 sec or <interval:int> sec 
        time.sleep(interval)

        try:
            page_state = driver.execute_script('return document.readyState')
        except Exception as e:
            print(e)

        # get time after waiting for script
        post_check_time = datetime.now()

        # get seconds between checks
        time_to_add = (post_check_time - pre_check_time).total_seconds()

        print(f'document state is {page_state}')
        if page_state == 'complete':
            resolved = True
        
        wait_time += time_to_add
    
    # interacting with page if available
    if resolved:
        interact_with_page(driver)

    return resolved




def get_data(
        driver: object, 
        browser: str='chrome',
        interval: int=1, 
        max_wait_time: int=30, 
        min_wait_time: int=3
    ) -> dict:
    """
    Once the page has loaded, grabs the
    page-source (html) and console-logs (logs).

    Expects: {
        'driver'        : object, 
        'browser'       : str, 
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
    logs = []

    # waiting for page to load
    driver_wait(
        driver=driver,
        interval=interval,
        max_wait_time=max_wait_time,
        min_wait_time=min_wait_time
    )

    # get page_source from browser
    try:
        html = driver.page_source
    except Exception as e:
        print(e)
    
    # get console logs if chrome
    if browser == 'chrome':
        try:
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



    