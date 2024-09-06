from .driver import driver_init, driver_wait, quit_driver
from .issuer import Issuer
import time, uuid, json, boto3, os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from ..models import * 
from datetime import datetime
from asgiref.sync import sync_to_async
from scanerr import settings






class Caser():
    """ 
    Run a `Testcase` for a specific `Site`.

    Expects: {
        'testcase' : object,
    }

    - Use `Caser.run()` to run case as Testcase

    Returns -> None
    """




    def __init__(self, testcase: object=None):
        self.testcase = testcase
        self.site_url = self.testcase.site.site_url
        self.steps = self.testcase.steps
        self.case_name = self.testcase.case.name
        self.configs = self.testcase.configs
        self.s_keys = {
            '+':            Keys.ADD,
            'Alt':          Keys.ALT,
            'ArrowDown':    Keys.ARROW_DOWN,
            'ArrowLeft':    Keys.ARROW_LEFT,
            'ArrowRight':   Keys.ARROW_RIGHT,
            'ArrowUp':      Keys.ARROW_UP,
            'Backspace':    Keys.BACKSPACE,
            'Control':      Keys.CONTROL,
            '.':            Keys.DECIMAL,
            'Delete':       Keys.DELETE,
            '/':            Keys.DIVIDE,
            'Enter':        Keys.ENTER,
            '=':            Keys.EQUALS,
            'Escape':       Keys.ESCAPE,
            'Meta':         Keys.META,
            '*':            Keys.MULTIPLY,
            '0':            Keys.NUMPAD0,
            '1':            Keys.NUMPAD1,
            '2':            Keys.NUMPAD2,
            '3':            Keys.NUMPAD3,
            '4':            Keys.NUMPAD4,
            '5':            Keys.NUMPAD5,
            '6':            Keys.NUMPAD6,
            '7':            Keys.NUMPAD7,
            '8':            Keys.NUMPAD8,
            '9':            Keys.NUMPAD9,
            ';':            Keys.SEMICOLON,
            'Shift':        Keys.SHIFT,
            'Space':        Keys.SPACE,
            '-':            Keys.SUBTRACT,
            'Tab':          Keys.TAB
        }




    def update_testcase(
            self, index: str=None, type: str=None, start_time: str=None, end_time: str=None, 
            passed: bool=None, exception: str=None, time_completed: str=None, image: str=None,
        ) -> None:
        # updates Tescase for a selenium run (async) 
        if start_time != None:
            self.testcase.steps[index][type]['time_created'] = str(start_time)
        if end_time != None:
            self.testcase.steps[index][type]['time_completed'] = str(end_time)
        if passed != None:
            self.testcase.steps[index][type]['passed'] = passed
        if exception != None:
            self.testcase.steps[index][type]['exception'] = str(exception)
        if image != None:
            self.testcase.steps[index][type]['image'] = str(image)
        if time_completed != None:
            self.testcase.time_completed = time_completed
            test_status = True
            for step in self.testcase.steps:
                if step['action']['passed'] == False:
                    test_status = False
                if step['assertion']['passed'] == False:
                    test_status = False
            self.testcase.passed = test_status
        
        self.testcase.save()
        return




    def format_element(self, element):
        elememt = json.dumps(element).rstrip('"').lstrip('"')
        return str(element)




    def save_screenshot(self) -> str:
        '''
        Grabs & uploads a screenshot of the `page` 
        passed in the params. 

        Returns -> `image_url` <str:remote path to image>
        '''

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # setting id for image
        pic_id = uuid.uuid4()
        
        # get screenshot
        self.driver.save_screenshot(f'{pic_id}.png')

        # seting up paths
        image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
        remote_path = f'static/testcases/{self.testcase.id}/{pic_id}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(image, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
        # remove local copy
        os.remove(image)

        # returning image url
        return image_url



    
    def get_element(self, selector: str=None, xpath: str=None) -> object:
        """ 
        Tries to get element by selector first and 
        then by xpath. If both fail, then return
        None for "element" and True for "failed".

        Expects: {
            "selector": str, 
            "xpath": str, 
        }

        Returns -> data: {
            'element': object | None,
            'failed': bool
        }
        """

        # defaults
        failed = True
        element = None

        # try selector first
        if selector:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                failed = False
            except:
                pass
        # try xpath as backup
        if xpath:
            try:
                element = self.driver.find_element(By.XPATH, xpath)
                failed = False
            except:
                pass

        # return data
        data = {
            'element': element,
            'failed': failed
        }
        return data

    


    def format_exception(self, exception: str) -> str:
        """ 
        Cleans the passed `exception` of any 
        system refs and unnecessary info

        Expects: {
            "exception": str
        }

        Returns -> str
        """

        split_e = str(exception).split('Stacktrace:')
        new_exception = split_e[0]

        return new_exception

    


    def run(self) -> None:
        """
        Runs the self.testcase using selenium as the driver

        Returns -> None
        """

        print(f'beginning testcase for {self.site_url} using case {self.case_name}')
        
        # initate driver
        self.driver = driver_init(
            browser=self.configs.get('browser', 'chrome'),
            window_size=self.configs['window_size'], 
            device=self.configs['device']
        )

        # setting implict wait_time for driver
        self.driver.implicitly_wait(self.configs['max_wait_time'])

        i = 0
        for step in self.steps:
            print(f'-- running step #{i+1} --')
        
            # adding catch if nav is not first
            if i == 0 and step['action']['type'] != 'navigate':
                print(f'navigating to {self.site_url} before first step')
                # using selenium, navigate to site root path & wait for page to load
                self.driver.get(f'{self.site_url}')
                time.sleep(int(self.configs['min_wait_time']))

            if step['action']['type'] == 'navigate':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )

                try:
                    print(f'navigating to {self.site_url}{step["action"]["path"]}')
                    # using selenium, navigate to requested path & wait for page to load
                    driver_wait(
                        driver=self.driver, 
                        interval=int(self.configs.get('interval', 1)),  
                        min_wait_time=int(self.configs.get('min_wait_time', 3)),
                        max_wait_time=int(self.configs.get('max_wait_time', 30)),
                    )
                    self.driver.get(f'{self.site_url}{step["action"]["path"]}')
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot()

                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )

            
            if step['action']['type'] == 'scroll':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )

                try:
                    print(f'scrolling -> {step["action"]["value"]}')
                                    
                    # scrolling using plain JavaScript
                    self.driver.execute_script(f'window.scrollTo({step["action"]["value"]});')
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # get image
                    image = self.save_screenshot()
                
                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )
        
            
            if step['action']['type'] == 'click':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )

                try:
                    print(f'clicking element -> {step["action"]["element"]}')
                    # using selenium, find and click on the 'element' 
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')
                                    
                    # scrolling to element using plain JavaScript
                    self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    self.driver.execute_script("window.scrollBy(0, -100);")
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # clicking element
                    element.click()
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot()
                
                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )
        
            if step['action']['type'] == 'change':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )
                
                try:
                    print(f'changing element to value -> {step["action"]["value"]}') 
                    # using selenium, find and change the 'element'.value
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element and back down a bit
                    self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    self.driver.execute_script("window.scrollBy(0, -100);")
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # changing value of element
                    value = step["action"]["value"]
                    element.send_keys(value)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot()
                
                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )

            if step['action']['type'] == 'keyDown':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )
                
                try:
                    print(f'keyDown action for key -> {step["action"]["key"]}')
                    # getting last known element
                    n = (i - 1)
                    elm = None
                    while True:
                        elm = self.steps[n]['action']['element']['selector']
                        if elm != None and len(elm) != 0:
                            break
                        n -= 1
                    selector = self.format_element(elm)
                                
                    # using selenium, find elemenmtn and send 'Key' event
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element and back down a bit
                    self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    self.driver.execute_script("window.scrollBy(0, -100);")
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # using selenium, press the selected key
                    element.send_keys(self.s_keys.get(step["action"]["key"], step["action"]["key"]))
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot()
                
                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )

            if step['assertion']['type'] == 'match':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='assertion', 
                    start_time=datetime.now()
                )

                try:
                    # using selenium, find elememt and assert if element.text == assertion.value
                    print(f'asserting that element value -> {step["assertion"]["element"]} matches {step["assertion"]["value"]}')
                    selector = self.format_element(step["assertion"]["element"]["selector"])
                    xpath = self.format_element(step["assertion"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element and back down a bit
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    self.driver.execute_script("window.scrollBy(0, -100);")
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # gettintg elem text
                    elementText = element.get_attribute('innerText')
                    elementText = element.text if len(elementText) == 0 else elementText
                    elementText = elementText.strip()
                    print(f'elementText -> {elementText}')
                    print(f'value -> {step["assertion"]["value"]}')

                    # assert text
                    if elementText != step["assertion"]["value"]:
                        raise AssertionError(f'innerText of element "{selector}" does match "{step['assertion']['value']}"')
                    
                    # save screenshot
                    image = self.save_screenshot()

                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )
            
            if step['assertion']['type'] == 'exists':
                exception = None
                passed = True
                self.update_testcase(
                    index=i, type='assertion', 
                    start_time=datetime.now()
                )

                try:
                    print(f'asserting that element -> {step["assertion"]["element"]} exists')
                    # find elememt and assert it exists
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element and back down a bit
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    self.driver.execute_script("window.scrollBy(0, -100);")
                    
                    # scrolling to element using plain JavaScript
                    self.driver.execute_script("arguments[0].scrollIntoView();", element)
                    image = self.save_screenshot()

                except Exception as e:
                    image = self.save_screenshot()
                    exception = self.format_exception(e)
                    passed = False

                self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )

            i += 1  

        self.update_testcase(
            time_completed=datetime.now()
        )
        quit_driver(driver=self.driver)
        print('-- testcase run complete --')
        
        if not self.testcase.passed and self.testcase.configs.get('create_issue'):
            print('generating new Issue...')
            Issuer(testcase=self.testcase).build_issue()
        
        return None


    
    
    