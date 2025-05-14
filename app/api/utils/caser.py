from asgiref.sync import sync_to_async
from cryptography.fernet import Fernet
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .driver import driver_init, driver_wait, quit_driver
from .issuer import Issuer
from .updater import update_flowrun
from .imager import Imager
from ..models import * 
from cursion import settings
from datetime import datetime, timezone
import time, uuid, json, boto3, os, requests






class Caser():
    """ 
    Run a `CaseRun` for a specific `Site` or 
    gather element info for new `Case`.

    Expects: {
        'caserun'       : object,
        'case'          : object,
        'process'       : object,
        'flowrun_id'    : str,
        'node_index'    : str,
    }

    - Use `Caser.run()` to run Case as CaseRun
    - Use `Caser.pre_run()` to run gather element info for a new Case 

    Returns -> None
    """




    def __init__(
            self, 
            case       : object=None, 
            caserun    : object=None,
            process    : object=None,
            flowrun_id : str=None,
            node_index : str=None,
        ):
       
        # primary objects
        self.case = case
        self.caserun = caserun
        self.process = process
        
        # secondary objects
        self.site_url = self.caserun.site.site_url if self.caserun else self.case.site.site_url
        self.steps = self.caserun.steps if self.caserun else requests.get(self.case.steps['url']).json()
        self.configs = self.caserun.configs if self.caserun else settings.CONFIGS
        self.flowrun_id = flowrun_id
        self.node_index = node_index
        self.account = self.case.account if self.case else self.caserun.account
        self.secrets = Secret.objects.filter(account=self.account)

        # init driver
        self.driver = driver_init(
            browser=self.configs.get('browser', 'chrome'),
            window_size=self.configs.get('window_size'), 
            device=self.configs.get('device')
        )

        # Selenium Keys reference
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

        # common scripts 
        self.scroll_to_center = (
            """
            const scrollToCenter = (elem) => {
                const rect = elem.getBoundingClientRect();
                const absoluteElementTop = rect.top + window.pageYOffset;
                const middle = absoluteElementTop - (window.innerHeight / 2) + (rect.height / 2);
                window.scrollTo({top: middle, behavior: 'instant'});
                setTimeout(function() {return null}, 300);
            }
            return scrollToCenter(arguments[0])
            """
        )

        # update flowrun
        if self.flowrun_id:
            update_flowrun(**{
                'flowrun_id': self.flowrun_id,
                'node_index': self.node_index,
                'message': (
                    f'starting up driver for case run using {self.configs.get('browser', 'chrome')}'
                ),
                'object_id': str(self.caserun.id)
            })




    def transpose_data(self, string: str=None) -> str:
        """ 
        Using replaces all vairables in string with 
        account `Secrets`.

        Expects: {
            'string' : str (to be transposed)
        }

        Returns -> transposed string
        """

        # decryption helper
        def decrypt_secret(value):
            f = Fernet(settings.SECRETS_KEY)
            decoded = f.decrypt(value)
            return decoded.decode('utf-8')

        # create secrets_list
        secrets_list = []
        for secret in self.secrets:
            secrets_list.append({
                'key': '{{'+str(secret.name)+'}}',
                'value': decrypt_secret(secret.value)
            })
        
        # iterate through secrets and replace data 
        for item in secrets_list:
            string = string.replace(
                item['key'], 
                item['value']
            )
        
        # return transposed str
        return string




    def update_caserun(
            self, 
            index: str=None, 
            type: str=None, 
            start_time: str=None, 
            end_time: str=None, 
            status: str=None, 
            exception: str=None, 
            time_completed: str=None, 
            image: str=None,
        ) -> None:

        # updates Tescase for a selenium run (async) 
        if start_time != None:
            self.caserun.steps[index][type]['time_created'] = str(start_time)
        if end_time != None:
            self.caserun.steps[index][type]['time_completed'] = str(end_time)
        if status != None:
            self.caserun.steps[index][type]['status'] = status
        if exception != None:
            self.caserun.steps[index][type]['exception'] = str(exception)
        if image != None:
            self.caserun.steps[index][type]['image'] = str(image)
        if time_completed != None:
            self.caserun.time_completed = time_completed
            run_status = 'passed'
            for step in self.caserun.steps:
                if step['action']['status'] == 'failed':
                    run_status = 'failed'
                if step['assertion']['status'] == 'failed':
                    run_status = 'failed'
            self.caserun.status = run_status
        
        # save caserun
        self.caserun.save()

        # compare image if image was passed
        if image is not None:
            self.compare_images(index=index, type=type)

        return None


    

    def compare_images(self, index: int=None, type: str=None) -> None:
        """ 
        Using Imager.caserun_vrt compare the step.screeshot 
        to the Case baseline.

        Expects: {
            'index' : int, step index
            'type'  : str, 'action' or 'assertion'
        }

        Returns: None
        """
        # run Imager
        image_delta_obj = Imager(caserun=self.caserun).caserun_vrt(step=index, type=type)

        # update caserun
        self.caserun.steps[index][type]['image_delta'] = image_delta_obj
        self.caserun.save()

        return None




    def update_process(
            self, 
            current: int, 
            total: int, 
            complete: bool=False, 
        ) -> None:
        """
        Calculates the current progress of the
        task based on current step and total 
        number of steps expected - then updates self.process
        with the info.

        Expects: {
            current     : int, 
            total       : int, 
            complete    : bool=False, 
        }

        Returns -> None
        """

        final_progress = 90
        progress = 0
        success = False
        if complete:
            progress = 100
            success = True
        if not complete:
            progress = float((current/total) * final_progress)

        print(f'updating process --> {progress}%')
        
        # update Process obj
        self.process.progress = progress
        self.process.success = success
        self.process.save()




    def format_element(self, element: object) -> str:
        elememt = json.dumps(element).rstrip('"').lstrip('"')
        return str(element)




    def save_screenshot(self, run_type: str=None) -> str:
        """
        Grabs & uploads a screenshot of the active `page` 
        self.driver is working on. 

        Expects: {
            run_type: str, 'run' or 'pre_run'
        }

        Returns -> `image_url` <str:remote path to image>
        """

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
        
        if run_type == 'run':
            remote_path = f'static/caseruns/{self.caserun.id}/{pic_id}.png'
        if run_type == 'pre_run':
            remote_path = f'static/case/{self.case.id}/{pic_id}.png'

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




    def save_case_steps(self, steps: dict, case_id: str) -> dict:
        """ 
        Helper function that uploads the "steps" data to 
        s3 bucket

        Expects: {
            'steps'   : dict, 
            'case_id' : str
        }

        Returns -> data: {
            'num_steps' : int,
            'url'       : str
        }
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # saving as json file temporarily
        steps_id = uuid.uuid4()
        with open(f'{steps_id}.json', 'w') as fp:
            json.dump(steps, fp)
        
        # seting up paths
        steps_file = os.path.join(settings.BASE_DIR, f'{steps_id}.json')
        remote_path = f'static/cases/{case_id}/{steps_id}.json'
        root_path = settings.AWS_S3_URL_PATH
        steps_url = f'{root_path}/{remote_path}'

        # upload to s3
        with open(steps_file, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={
                    'ACL': 'public-read', 
                    'ContentType': 'application/json',
                    'CacheControl': 'max-age=0'
                }
            )

        # remove local copy
        os.remove(steps_file)

        # format data
        data = {
            'num_steps': len(steps),
            'url': steps_url
        }

        # return response
        return data




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

    


    def get_element_image(self, element: object) -> str:
        """ 
        Grabs a screenshot of the passed "element"
        and returns image data as base64 str.

        Expects: {
            "element": object (REQUIRED)
        }

        Returns -> str (base64 encoded)
        """

        try:
            image = element.screenshot_as_base64
            # sleep for .5 seconds to let image process
            time.sleep(.5)
        except:
            image = None
        return image


    

    def run(self) -> None:
        """
        Runs the self.caserun using selenium as the driver

        Returns -> None
        """

        msg = f'starting case run for {self.site_url} using case "{self.caserun.title}" | run_id: {str(self.caserun.id)}'
        print(msg)

        # update flowrun
        if self.flowrun_id:
            update_flowrun(**{
                'flowrun_id': self.flowrun_id,
                'node_index': self.node_index,
                'message': msg,
                'objects': [{
                    'parent': str(self.caserun.site.id),
                    'id': str(self.caserun.id),
                    'status': 'working'
                }]
            })
        
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
            msg = f'running step #{i+1} | run_id: {str(self.caserun.id)}'
            
            # update flowrun
            if self.flowrun_id:
                update_flowrun(**{
                    'flowrun_id': self.flowrun_id,
                    'node_index': self.node_index,
                    'message': msg
                })
        
            # adding catch if nav is not first
            if i == 0 and step['action']['type'] != 'navigate':
                print(f'navigating to {self.site_url} before first step')
                # using selenium, navigate to site root path & wait for page to load
                self.driver.get(f'{self.site_url}')
                time.sleep(int(self.configs['min_wait_time']))


            if step['action']['type'] == 'navigate':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='action', 
                    start_time=datetime.now(timezone.utc)
                )

                try:
                    msg = f'navigating to {self.site_url}{step["action"]["path"]} | run_id: {str(self.caserun.id)}'
                    print(msg)

                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': msg
                        })

                    # using selenium, navigate to requested path & wait for page to load
                    driver_wait(
                        driver=self.driver, 
                        interval=int(self.configs.get('interval', 1)),  
                        min_wait_time=int(self.configs.get('min_wait_time', 3)),
                        max_wait_time=int(self.configs.get('max_wait_time', 30)),
                    )
                    self.driver.get(f'{self.site_url}{step["action"]["path"]}')
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot(run_type='run')

                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    msg = excaption
                    status = 'failed'

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='action', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break


            if step['action']['type'] == 'scroll':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='action', 
                    start_time=datetime.now(timezone.utc)
                )

                try:
                    msg = f'scrolling ({step["action"]["value"]}) | run_id: {str(self.caserun.id)}'
                    print(msg)

                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message':msg
                        })
                                    
                    # scrolling using plain JavaScript
                    self.driver.execute_script(f'window.scrollTo({step["action"]["value"]});')
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # get image
                    image = self.save_screenshot(run_type='run')
                
                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='action', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break
        

            if step['action']['type'] == 'click':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='action', 
                    start_time=datetime.now(timezone.utc)
                )

                try:
                    msg = f'clicking element "{step["action"]["element"]["selector"]}" | run_id: {str(self.caserun.id)}'
                    print(msg)

                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message':msg
                        })

                    # using selenium, find and click on the 'element' 
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')
                                    
                    # scrolling to element using plain JavaScript
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # clicking element
                    element.click()
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot(run_type='run')
                
                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='action', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break
        

            if step['action']['type'] == 'change':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='action', 
                    start_time=datetime.now(timezone.utc)
                )
                
                try:
                    msg = f'changing element "{step["action"]["element"]["selector"]}" value to "{step["action"]["value"]}" | run_id: {str(self.caserun.id)}'
                    print(msg)

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': msg
                        })

                    # using selenium, find and change the 'element'.value
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element using plain javascript
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # changing value of element
                    value = self.transpose_data(step["action"]["value"])
                    element.send_keys(value)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot(run_type='run')
                
                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'
                
                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='action', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break


            if step['action']['type'] == 'keyDown':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='action', 
                    start_time=datetime.now(timezone.utc)
                )
                
                try:
                    msg = f'keyDown action using key "{step["action"]["key"]}" | run_id: {str(self.caserun.id)}'
                    print(msg)

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': msg
                        })

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

                    # scrolling to element using plain javascript
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # using selenium, press the selected key
                    element.send_keys(self.s_keys.get(step["action"]["key"], step["action"]["key"]))
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                    image = self.save_screenshot(run_type='run')
                
                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='action', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break


            if step['assertion']['type'] == 'match':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='assertion', 
                    start_time=datetime.now(timezone.utc)
                )

                try:
                    # using selenium, find elememt and assert if element.text == assertion.value
                    msg = f'asserting that element "{step["assertion"]["element"]["selector"]}".innerText matches "{step["assertion"]["value"]}" | run_id: {str(self.caserun.id)}' 
                    print(msg)

                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': msg
                        })

                    selector = self.format_element(step["assertion"]["element"]["selector"])
                    xpath = self.format_element(step["assertion"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # gettintg elem text
                    elementText = element.get_attribute('innerText')
                    elementText = element.text if len(elementText) == 0 else elementText
                    elementText = elementText.strip()
                    print(f'elementText -> {elementText}')
                    print(f'value -> {step["assertion"]["value"]}')

                    # assert text
                    if elementText != self.transpose_data(step["assertion"]["value"]):
                        raise AssertionError(f'innerText of element "{selector}" does match expected')
                    
                    # save screenshot
                    image = self.save_screenshot(run_type='run')

                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'

                    # update flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                # update caserun
                self.update_caserun(
                    index=i, type='assertion', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break
            

            if step['assertion']['type'] == 'exists':
                exception = None
                status = 'passed'
                self.update_caserun(
                    index=i, type='assertion', 
                    start_time=datetime.now(timezone.utc)
                )

                try:
                    msg = f'asserting that {step["assertion"]["element"]["selector"]} exists | run_id: {str(self.caserun.id)}'
                    print(msg)
                    
                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': msg
                        })

                    # find elememt and assert it exists
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element
                    self.driver.execute_script(self.scroll_to_center, element)
                    
                    # get step screenshot
                    image = self.save_screenshot(run_type='run')

                except Exception as e:
                    image = self.save_screenshot(run_type='run')
                    exception = self.format_exception(e)
                    status = 'failed'

                    # updating flowrun
                    if self.flowrun_id:
                        update_flowrun(**{
                            'flowrun_id': self.flowrun_id,
                            'node_index': self.node_index,
                            'message': f'❌ {exception} | run_id: {str(self.caserun.id)}'
                        })

                self.update_caserun(
                    index=i, type='assertion', 
                    end_time=datetime.now(timezone.utc), 
                    status=status, 
                    exception=exception,
                    image=image
                )

                # exit early if configs.end_on_fail == True
                if self.caserun.configs.get('end_on_fail', True) and status == 'failed':
                    break

            i += 1  

        self.update_caserun(
            time_completed=datetime.now(timezone.utc)
        )
        quit_driver(driver=self.driver)
        print('-- caserun run complete --')

        # update flowrun
        if self.flowrun_id:
            update_flowrun(**{
                'flowrun_id': self.flowrun_id,
                'node_index': self.node_index,
                'message': (
                    f'case run "{self.caserun.title}" for {self.caserun.site.site_url} completed with status: '+
                    f'{"❌ FAILED" if self.caserun.status == 'failed' else "✅ PASSED"} | run_id: {str(self.caserun.id)}'
                ),
                'objects': [{
                    'parent': str(self.caserun.site.id),
                    'id': str(self.caserun.id),
                    'status': self.caserun.status
                }],
                'node_status': self.caserun.status
            })
        
        if self.caserun.status == 'failed' and self.caserun.configs.get('create_issue'):
            print('generating new Issue...')
            Issuer(caserun=self.caserun).build_issue()
        
        return None




    def pre_run(self) -> None:
        """
        Runs the self.case using selenium as the driver
        and tries to collect element img & screenshot data.

        Returns -> None
        """

        print(f'beginning pre_run for Case {self.case.title}')

        # setting implict wait_time for driver
        self.driver.implicitly_wait(self.configs.get('max_wait_time'))

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

                except Exception as e:
                    print(e)

                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['action']['image'] = img_url


            
            if step['action']['type'] == 'scroll':
                try:
                    print(f'scrolling -> {step["action"]["value"]}')     
                    # scrolling using plain JavaScript
                    self.driver.execute_script(f'window.scrollTo({step["action"]["value"]});')
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                
                except Exception as e:
                    print(e)
                
                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['action']['image'] = img_url
        
            
            if step['action']['type'] == 'click':
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
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # get elem img & update self.steps
                    if not self.steps[i]['action'].get('img'):
                        img = self.get_element_image(element)
                        self.steps[i]['action']['img'] = img

                    # clicking element
                    element.click()
                    time.sleep(int(self.configs.get('min_wait_time', 3)))
                
                except Exception as e:
                    print(e)

                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['action']['image'] = img_url
        
        
            if step['action']['type'] == 'change':
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

                    # scrolling to element using plain javascript
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # get elem img & update self.steps
                    if not self.steps[i]['action'].get('img'):
                        img = self.get_element_image(element)
                        self.steps[i]['action']['img'] = img

                    # changing value of element
                    value = step["action"]["value"]
                    element.send_keys(value)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                except Exception as e:
                    print(e)

                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['action']['image'] = img_url


            if step['action']['type'] == 'keyDown':
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
                                
                    # using selenium, find element and send 'Key' event
                    selector = self.format_element(step["action"]["element"]["selector"])
                    xpath = self.format_element(step["action"]["element"]["xpath"])
                    element_data = self.get_element(selector, xpath)
                    element = element_data['element']

                    # checking if element was found
                    if element_data['failed']:
                        raise Exception(f'Unable to locate element with the given Selector and xPath')

                    # scrolling to element using plain javascript
                    self.driver.execute_script(self.scroll_to_center, element)
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                    # get elem img & update self.steps
                    if not self.steps[i]['action'].get('img'):
                        img = self.get_element_image(element)
                        self.steps[i]['action']['img'] = img

                    # using selenium, press the selected key
                    element.send_keys(self.s_keys.get(step["action"]["key"], step["action"]["key"]))
                    time.sleep(int(self.configs.get('min_wait_time', 3)))

                except Exception as e:
                    print(e)

                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['action']['image'] = img_url


            if step['assertion']['type'] == 'match':
                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['assertion']['image'] = img_url

            
            if step['assertion']['type'] == 'exists':
                # get screenshot and save
                img_url = self.save_screenshot(run_type='pre_run')
                self.steps[i]['assertion']['image'] = img_url
            

            # increment step
            i += 1  

            # update process
            self.update_process(
                current=(i+1), 
                total=self.case.steps['num_steps'], 
                complete=False
            )


        # update case
        steps_data = self.save_case_steps(self.steps, str(self.case.id))
        self.case.steps = steps_data
        self.case.processed = True
        self.case.save()

        quit_driver(driver=self.driver)
        print('-- case pre_run complete --')
        
        # update process
        self.update_process(current=1, total=1, complete=True)
        
        return None




    
    