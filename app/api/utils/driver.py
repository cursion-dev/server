from selenium import webdriver
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from .devices import get_device
from datetime import datetime
import time, os, sys, tempfile






def driver_init(
        browser         : str='chrome',
        window_size     : str='1920,1080', 
        device          : str='Windows 10 PC',
        pixel_ratio     : int=1.0,
        scale_factor    : int=0.5
    ) -> object:
    """ 
    Starts a new selenium driver instance

    Args:
        'browser'       : str,
        'window_size'   : str, 
        'device'        : str,
        'script_timeout': int,
        'load_timeout'  : int,
        'wait_time'     : int, 
        'pixel_ratio'   : int,
        'scale_factor'  : int

    Returns: driver object
    """

    # get userAgent 
    user_agent = get_device(browser, device)['user_agent']

    # deciding on browser
    # UserAgents are from utils/devices
    if browser == 'chrome':
        options = webdriver.ChromeOptions()
        options.binary_location = os.environ.get('CHROME_BROWSER')
    if browser == 'firefox':
        options = webdriver.FirefoxOptions()
        options.binary_location = os.environ.get('FIREFOX_BROWSER')
    if browser == 'edge':
        options = webdriver.EdgeOptions()
        options.binary_location = os.environ.get('EDGE_BROWSER')

    # setting up browser configs
    sizes = window_size.split(',')
    width = int(sizes[0])
    height = int(sizes[1])
    emulation = {
        "deviceMetrics": { 
            "width": width, 
            "height": height,
            "pixelRatio": pixel_ratio 
        },
        "userAgent": user_agent
    }

    # setting broswer options for chrome
    if browser == 'chrome':
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--use-gl=swiftshader")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--hide-scrollbars")
        options.add_argument(f"--force-device-scale-factor={str(scale_factor)}")
        options.add_argument(f"--user-agent={user_agent}")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        options.page_load_strategy = 'none'
        
        # setting to mobile or tablet if reqeusted
        if device == 'mobile' or device == 'tablet':
            options.add_experimental_option("mobileEmulation", emulation)
        
        # init driver
        driver = webdriver.Chrome(options=options)
    
    # setting broswer options for firefox
    if browser == 'firefox':
        # setting profile 
        temp_profile_dir = tempfile.mkdtemp()
        ff_profile = FirefoxProfile(temp_profile_dir)
        # adding arguments
        options.add_argument("-headless")
        options.page_load_strategy = 'none'
        options.set_preference("accept_insecure_certs", True)
        options.set_preference('layout.css.devPixelsPerPx', str(scale_factor))
        options.profile = ff_profile

        # setting to mobile if reqeusted
        if device == 'mobile':
            options.set_preference(
                "general.useragent.override", f"userAgent={user_agent}"
            )
        
        # init driver
        driver = webdriver.Firefox(options=options)

    # setting broswer options for edge
    if browser == 'edge':
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--use-gl=swiftshader")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--hide-scrollbars")
        options.add_argument(f"--force-device-scale-factor={str(scale_factor)}")
        options.add_argument(f"--user-agent={user_agent}")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        options.page_load_strategy = 'none'
        
        # setting to mobile or tablet if reqeusted
        if device == 'mobile' or device == 'tablet':
            options.add_experimental_option("mobileEmulation", emulation)
        
        # init driver
        driver = webdriver.Edge(options=options)

    # resizing window
    driver.maximize_window()
    driver.set_window_size(width, height)
    print(f'Using {browser} browser')

    return driver




def driver_test() -> None:
    """ 
    Spins up a selenium driver instance and
    tests to ensure it can access the browser and internet

    Returns: None
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

    Args:
        'driver'        : object, 
        'interval'      : int,
        'max_wait_time' : int,
        'min_wait_time' : int
    
    Returns: bool (True if page is loaded)
    """

    def interact_with_page(driver):
        # simulate mouse movement
        action = ActionBuilder(driver)
        action.pointer_action.move_to_location(0, 0)
        action.perform()
        # wait for 1s
        time.sleep(0.5)
        action.pointer_action.move_to_location(0, 50)
        action.perform()
        # wait for 1s
        time.sleep(0.5)
        action.pointer_action.move_to_location(0, 0)
        action.perform()
        return

    resolved = False
    page_state = 'loading'
    wait_time = 0

    # min_wait_time before checking page status
    time.sleep(int(min_wait_time))

    while int(wait_time) < int(max_wait_time) and page_state != 'complete':

        # get current timestamp
        pre_check_time = datetime.now()
        
        # wait 1 sec or <interval:int> sec 
        time.sleep(int(interval))

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

    Args:
        'driver'        : object, 
        'browser'       : str, 
        'interval'      : int,
        'max_wait_time' : int,
        'min_wait_time' : int

    Returns:
        'html' : str,
        'logs' : dict
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

    def is_ignorable_warning(log_entry: object) -> bool:
        ignore_list = [
            "WebGL", "GL Driver Message", "GPU", "No available adapters",
        ]
        try:
            message = (log_entry or {}).get("message", "")
        except Exception:
            return False
        for i in ignore_list:
            if i in message:
                return True
        return False

    # get page_source from browser
    try:
        html = driver.page_source
    except Exception as e:
        print(e)
    
    # get console logs if notn firefox
    if browser != 'firefox' :
        try:
            logs = driver.get_log('browser')
            logs = [entry for entry in logs if not is_ignorable_warning(entry)]
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

    Returns: None
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



    
