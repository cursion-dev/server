# from .driver_p import driver_init as driver_p_init
# from .driver_s import driver_init as driver_init
# from .driver_s import driver_wait, quit_driver
# from .issuer import Issuer
# import time, uuid, json, boto3, os
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from ..models import * 
# from datetime import datetime
# from asgiref.sync import sync_to_async
# from cursion import settings






# class Caser():
#     """ 
#     Run a `Testcase` for a specific `Site`.

#     Expects: {
#         'testcase' : object,
#     }

#     - Use `Caser.run_s()` to run with selenium
#     - Use `Caser.run_p()` to run with puppeteer

#     Returns -> None
#     """




#     def __init__(self, testcase: object=None):
#         self.testcase = testcase
#         self.site_url = self.testcase.site.site_url
#         self.steps = self.testcase.steps
#         self.case_name = self.testcase.case.name
#         self.configs = self.testcase.configs
#         self.s_keys = {
#             '+':            Keys.ADD,
#             'Alt':          Keys.ALT,
#             'ArrowDown':    Keys.ARROW_DOWN,
#             'ArrowLeft':    Keys.ARROW_LEFT,
#             'ArrowRight':   Keys.ARROW_RIGHT,
#             'ArrowUp':      Keys.ARROW_UP,
#             'Backspace':    Keys.BACKSPACE,
#             'Control':      Keys.CONTROL,
#             '.':            Keys.DECIMAL,
#             'Delete':       Keys.DELETE,
#             '/':            Keys.DIVIDE,
#             'Enter':        Keys.ENTER,
#             '=':            Keys.EQUALS,
#             'Escape':       Keys.ESCAPE,
#             'Meta':         Keys.META,
#             '*':            Keys.MULTIPLY,
#             '0':            Keys.NUMPAD0,
#             '1':            Keys.NUMPAD1,
#             '2':            Keys.NUMPAD2,
#             '3':            Keys.NUMPAD3,
#             '4':            Keys.NUMPAD4,
#             '5':            Keys.NUMPAD5,
#             '6':            Keys.NUMPAD6,
#             '7':            Keys.NUMPAD7,
#             '8':            Keys.NUMPAD8,
#             '9':            Keys.NUMPAD9,
#             ';':            Keys.SEMICOLON,
#             'Shift':        Keys.SHIFT,
#             'Space':        Keys.SPACE,
#             '-':            Keys.SUBTRACT,
#             'Tab':          Keys.TAB
#         }




#     @sync_to_async
#     def update_testcase(
#             self, index: str=None, type: str=None, start_time: str=None, end_time: str=None, 
#             passed: bool=None, exception: str=None, time_completed: str=None, image: str=None,
#         ) -> None:
#         # updates Tescase for a puppeteer run (async) 
#         if start_time != None:
#             self.testcase.steps[index][type]['time_created'] = str(start_time)
#         if end_time != None:
#             self.testcase.steps[index][type]['time_completed'] = str(end_time)
#         if passed != None:
#             self.testcase.steps[index][type]['passed'] = passed
#         if exception != None:
#             self.testcase.steps[index][type]['exception'] = str(exception)
#         if image != None:
#             self.testcase.steps[index][type]['image'] = str(image)
#         if time_completed != None:
#             self.testcase.time_completed = time_completed
#             test_status = True
#             for step in self.testcase.steps:
#                 if step['action']['passed'] == False:
#                     test_status = False
#                 if step['assertion']['passed'] == False:
#                     test_status = False
#             self.testcase.passed = test_status
        
#         self.testcase.save()
#         return None




#     def update_testcase_s(
#             self, index: str=None, type: str=None, start_time: str=None, end_time: str=None, 
#             passed: bool=None, exception: str=None, time_completed: str=None, image: str=None,
#         ) -> None:
#         # updates Tescase for a selenium run (async) 
#         if start_time != None:
#             self.testcase.steps[index][type]['time_created'] = str(start_time)
#         if end_time != None:
#             self.testcase.steps[index][type]['time_completed'] = str(end_time)
#         if passed != None:
#             self.testcase.steps[index][type]['passed'] = passed
#         if exception != None:
#             self.testcase.steps[index][type]['exception'] = str(exception)
#         if image != None:
#             self.testcase.steps[index][type]['image'] = str(image)
#         if time_completed != None:
#             self.testcase.time_completed = time_completed
#             test_status = True
#             for step in self.testcase.steps:
#                 if step['action']['passed'] == False:
#                     test_status = False
#                 if step['assertion']['passed'] == False:
#                     test_status = False
#             self.testcase.passed = test_status
        
#         self.testcase.save()
#         return




#     @sync_to_async
#     def format_element(self, element):
#         elememt = json.dumps(element).rstrip('"').lstrip('"')
#         return str(element)




#     def format_element_s(self, element):
#         elememt = json.dumps(element).rstrip('"').lstrip('"')
#         return str(element)



    
#     async def save_screenshot(self, page: object=None) -> str:
#         '''
#         Grabs & uploads a screenshot of the `page` 
#         passed in the params. 

#         Returns -> `image_url` <str:remote path to image>
#         '''

#         # setup boto3 configurations
#         s3 = boto3.client(
#             's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
#             aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
#             region_name=str(settings.AWS_S3_REGION_NAME), 
#             endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
#         )

#         # setting id for image
#         pic_id = uuid.uuid4()
        
#         # get screenshot
#         await page.screenshot({'path': f'{pic_id}.png'})

#         # seting up paths
#         image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
#         remote_path = f'static/testcases/{self.testcase.id}/{pic_id}.png'
#         root_path = settings.AWS_S3_URL_PATH
#         image_url = f'{root_path}/{remote_path}'
    
#         # upload to s3
#         with open(image, 'rb') as data:
#             s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
#                 remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
#             )
#         # remove local copy
#         os.remove(image)

#         # returning image url
#         return image_url



    
#     def save_screenshot_s(self) -> str:
#         '''
#         Grabs & uploads a screenshot of the `page` 
#         passed in the params. 

#         Returns -> `image_url` <str:remote path to image>
#         '''

#         # setup boto3 configurations
#         s3 = boto3.client(
#             's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
#             aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
#             region_name=str(settings.AWS_S3_REGION_NAME), 
#             endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
#         )

#         # setting id for image
#         pic_id = uuid.uuid4()
        
#         # get screenshot
#         self.driver.save_screenshot(f'{pic_id}.png')

#         # seting up paths
#         image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
#         remote_path = f'static/testcases/{self.testcase.id}/{pic_id}.png'
#         root_path = settings.AWS_S3_URL_PATH
#         image_url = f'{root_path}/{remote_path}'
    
#         # upload to s3
#         with open(image, 'rb') as data:
#             s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
#                 remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
#             )
#         # remove local copy
#         os.remove(image)

#         # returning image url
#         return image_url



#     @sync_to_async
#     def format_exception(self, exception: str) -> str:
#         """ 
#         Cleans the passed `exception` of any 
#         system refs and unnecessary info

#         Expects: {
#             "exception": str
#         }

#         Returns -> str
#         """

#         split_e = str(exception).split('Stacktrace:')
#         new_exception = split_e[0]

#         return new_exception


    

#     def format_exception_s(self, exception: str) -> str:
#         """ 
#         Cleans the passed `exception` of any 
#         system refs and unnecessary info

#         Expects: {
#             "exception": str
#         }

#         Returns -> str
#         """

#         split_e = str(exception).split('Stacktrace:')
#         new_exception = split_e[0]

#         return new_exception

    


#     def run_s(self) -> None:
#         """
#         Runs the self.testcase using selenium as the driver

#         Returns -> None
#         """

#         print(f'beginning testcase for {self.site_url}  \
#             using case {self.case_name}')
        
#         # initate driver
#         self.driver = driver_init(
#             window_size=self.configs['window_size'], 
#             device=self.configs['device']
#         )

#         # setting implict wait_time for driver
#         self.driver.implicitly_wait(self.configs['max_wait_time'])

#         i = 0
#         for step in self.steps:
#             print(f'-- running step #{i+1} --')
        
#             # adding catch if nav is not first
#             if i == 0 and step['action']['type'] != 'navigate':
#                 print(f'navigating to {self.site_url} before first step')
#                 # using selenium, navigate to site root path & wait for page to load
#                 self.driver.get(f'{self.site_url}')
#                 time.sleep(int(self.configs['min_wait_time']))

#             if step['action']['type'] == 'navigate':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'navigating to {self.site_url}{step["action"]["path"]}')
#                     # using selenium, navigate to requested path & wait for page to load
#                     driver_wait(
#                         driver=self.driver, 
#                         interval=int(self.configs.get('interval', 1)),  
#                         min_wait_time=int(self.configs.get('min_wait_time', 3)),
#                         max_wait_time=int(self.configs.get('max_wait_time', 30)),
#                     )
#                     self.driver.get(f'{self.site_url}{step["action"]["path"]}')
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = self.save_screenshot_s()

#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

            
#             if step['action']['type'] == 'scroll':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'scrolling -> {step["action"]["value"]}')
                                    
#                     # scrolling using plain JavaScript
#                     self.driver.execute_script(f'window.scrollTo({step["action"]["value"]});')
#                     time.sleep(int(self.configs.get('min_wait_time', 3)))

#                     # get image
#                     image = self.save_screenshot_s()
                
#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )
        
            
#             if step['action']['type'] == 'click':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'clicking element -> {step["action"]["element"]}')
#                     # using selenium, find and click on the 'element' 
#                     selector = self.format_element_s(step["action"]["element"])
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    
#                     # scrolling to element using plain JavaScript
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     self.driver.execute_script("arguments[0].scrollIntoView();", element)
#                     self.driver.execute_script("window.scrollBy(0, -100);")
#                     time.sleep(int(self.configs.get('min_wait_time', 3)))

#                     # clicking element
#                     element.click()
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = self.save_screenshot_s()
                
#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )
        
#             if step['action']['type'] == 'change':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )
                
#                 try:
#                     print(f'changing element to value -> {step["action"]["value"]}') 
#                     # using selenium, find and change the 'element'.value
#                     selector = self.format_element_s(step["action"]["element"])
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)

#                     # scrolling to element and back down a bit
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     self.driver.execute_script("arguments[0].scrollIntoView();", element)
#                     self.driver.execute_script("window.scrollBy(0, -100);")
#                     time.sleep(int(self.configs.get('min_wait_time', 3)))

#                     # changing value of element
#                     value = step["action"]["value"]
#                     element.send_keys(value)
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = self.save_screenshot_s()
                
#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             if step['action']['type'] == 'keyDown':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )
                
#                 try:
#                     print(f'keyDown action for key -> {step["action"]["key"]}')
#                     # getting last known element
#                     n = (i - 1)
#                     elm = None
#                     while True:
#                         elm = self.steps[n]['action']['element']
#                         if elm != None and len(elm) != 0:
#                             break
#                         n -= 1
#                     selector = self.format_element_s(elm)
                                
#                     # using selenium, find elemenmtn and send 'Key' event
#                     selector = self.format_element_s(step["action"]["element"])
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)

#                     # scrolling to element and back down a bit
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     self.driver.execute_script("arguments[0].scrollIntoView();", element)
#                     self.driver.execute_script("window.scrollBy(0, -100);")
#                     time.sleep(int(self.configs.get('min_wait_time', 3)))

#                     # using selenium, press the selected key
#                     element.send_keys(self.s_keys.get(step["action"]["key"], step["action"]["key"]))
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = self.save_screenshot_s()
                
#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             if step['assertion']['type'] == 'match':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'asserting that element value -> {step["assertion"]["element"]} matches {step["assertion"]["value"]}')
#                     # using selenium, find elememt and assert if element.text == assertion.text
#                     selector = self.format_element_s(step["action"]["element"])
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)

#                     # scrolling to element and back down a bit
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     self.driver.execute_script("arguments[0].scrollIntoView();", element)
#                     self.driver.execute_script("window.scrollBy(0, -100);")
#                     time.sleep(int(self.configs.get('min_wait_time', 3)))

#                     # gettintg elem text
#                     elementText = self.driver.execute_script(f'return document.querySelector("{selector}").textContent')
#                     elementText = elementText.strip()
#                     print(f'elementText => {elementText}')
#                     print(f'value => {step["assertion"]["value"]}')

#                     # assert text
#                     assert elementText == step["assertion"]["value"]
#                     image = self.save_screenshot_s()

#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )
            
#             if step['assertion']['type'] == 'exists':
#                 exception = None
#                 passed = True
#                 self.update_testcase_s(
#                     index=i, type='assertion', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'asserting that element -> {step["assertion"]["element"]} exists')
#                     # using puppeteer, find elememt and assert it exists
#                     selector = self.format_element_s(step["action"]["element"])
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)

#                     # scrolling to element and back down a bit
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     self.driver.execute_script("arguments[0].scrollIntoView();", element)
#                     self.driver.execute_script("window.scrollBy(0, -100);")
                    
#                     # scrolling to element using plain JavaScript
#                     self.driver.execute_script(f'document.querySelector("{selector}").scrollIntoView()')
#                     element = self.driver.find_element(By.CSS_SELECTOR, selector)
#                     image = self.save_screenshot_s()

#                 except Exception as e:
#                     image = self.save_screenshot_s()
#                     exception = self.format_exception_s(e)
#                     passed = False

#                 self.update_testcase_s(
#                     index=i, type='assertion', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             i += 1  

#         self.update_testcase_s(
#             time_completed=datetime.now()
#         )
#         quit_driver(driver=self.driver)
#         print('-- testcase run complete --')
        
#         if not self.testcase.passed and self.testcase.configs.get('create_issue'):
#             print('generating new Issue...')
#             Issuer(testcase=self.testcase).build_issue()
        
#         return None




#     async def run_p(self) -> None:
#         """
#         Runs the self.testcase using pupeteer as the driver

#         Returns -> None
#         """

#         print(f'beginning testcase for {self.site_url}  \
#             using case {self.case_name}')
        
#         # initate driver
#         self.driver = await driver_p_init()
        
#         # init page obj 
#         self.page = await self.driver.newPage()

#         # setting up page with configs
#         sizes = self.configs['window_size'].split(',')
#         is_mobile = False
#         if self.configs['device'] == 'mobile':
#             is_mobile = True
        
#         self.page_options = {
#             'waitUntil': 'networkidle0', 
#             'timeout': int(self.configs['max_wait_time'])*1000
#         }

#         print(f'setting max timeout to -> {int(self.configs["max_wait_time"])}s')

#         viewport = {
#             'width': int(sizes[0]),
#             'height': int(sizes[1]),
#             'isMobile': is_mobile,
#         }
        
#         userAgent = (
#             "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
#             (KHTML, like Gecko) Chrome/99.0.4812.0 Mobile Safari/537.36"
#         )
        
#         emulate_options = {
#             'viewport': viewport,
#             'userAgent': userAgent
#         }

#         if self.configs['device'] == 'mobile':
#             await self.page.emulate(emulate_options)
#         else:
#             await self.page.setViewport(viewport)


#         i = 0
#         for step in self.steps:
#             print(f'-- running step #{i+1} --')

#             # adding catch if nav is not first
#             if i == 0 and step['action']['type'] != 'navigate':
#                 print(f'navigating to {self.site_url} before first step')
#                 # using puppeteer, navigate to site root path & wait for page to load
#                 await self.page.goto(f'{self.site_url}', self.page_options)
#                 time.sleep(int(self.configs['min_wait_time']))

#             if step['action']['type'] == 'navigate':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'navigating to {self.site_url}{step["action"]["path"]}')
#                     # using puppeteer, navigate to requested path & wait for page to load
#                     await self.page.goto(f'{self.site_url}{step["action"]["path"]}', self.page_options)
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = await self.save_screenshot(page=self.page)

#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

                
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             if step['action']['type'] == 'scroll':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'scrolling -> {step["action"]["value"]}')
              
#                     # scrolling using plain JavaScript
#                     await self.page.evaluate(f'window.scrollTo({step["action"]["value"]});')
#                     time.sleep(int(self.configs['min_wait_time']))

#                     # get image
#                     image = await self.save_screenshot(page=self.page)
                
#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 ) 
               
#             if step['action']['type'] == 'click':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'clicking element -> {step["action"]["element"]}')
#                     # using puppeteer, find and click on the 'element' 
#                     selector = await self.format_element(step["action"]["element"])
#                     await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))                 
#                     # scrolling to element using plain JavaScript
#                     await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
#                     element = await self.page.J(selector)
#                     await element.click()
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = await self.save_screenshot(page=self.page)
                
#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 ) 

#             if step['action']['type'] == 'change':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )
                
#                 try:
#                     print(f'changing element to value -> {step["action"]["value"]}') 
#                     # using puppeteer, find and click on the 'element'
#                     if step["action"]["element"] != (None or ''):
#                         selector = await self.format_element(step["action"]["element"])
#                         await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
#                         # scrolling to element using plain JavaScript 
#                         await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
#                         element = await self.page.J(selector)
#                         await element.click(clickCount=3)
#                     await self.page.keyboard.type(step["action"]["value"])
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = await self.save_screenshot(page=self.page)
                
#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 ) 

#             if step['action']['type'] == 'keyDown':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='action', 
#                     start_time=datetime.now()
#                 )
                
#                 try:
#                     print(f'keyDown action for key -> {step["action"]["key"]}')
#                     # using puppeteer, press the selected key
#                     await self.page.keyboard.press(step['action']['key'])
#                     time.sleep(int(self.configs['min_wait_time']))
#                     image = await self.save_screenshot(page=self.page)
                
#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='action', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             if step['assertion']['type'] == 'match':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='assertion', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'asserting that element value -> {step["assertion"]["element"]} matches {step["assertion"]["value"]}')
#                     # using puppeteer, find elememt and assert if element.text == assertion.text
#                     selector = await self.format_element(step["assertion"]["element"])
#                     await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
#                     # scrolling to element using plain JavaScript
#                     await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
#                     elementText = await self.page.evaluate(f'document.querySelector("{selector}").textContent')
#                     elementText = elementText.strip()
#                     print(f'elementText => {elementText}')
#                     print(f'value => {step["assertion"]["value"]}')
#                     assert elementText == step["assertion"]["value"]
#                     image = await self.save_screenshot(page=self.page)

#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='assertion', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             if step['assertion']['type'] == 'exists':
#                 exception = None
#                 passed = True
#                 await self.update_testcase(
#                     index=i, type='assertion', 
#                     start_time=datetime.now()
#                 )

#                 try:
#                     print(f'asserting that element -> {step["assertion"]["element"]} exists')
#                     # using puppeteer, find elememt and assert it exists
#                     selector = await self.format_element(step["assertion"]["element"])
#                     await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
#                     await self.page.J(selector)
#                     image = await self.save_screenshot(page=self.page)

#                 except Exception as e:
#                     image = await self.save_screenshot(page=self.page)
#                     exception = await self.format_exception(e)
#                     passed = False

#                 await self.update_testcase(
#                     index=i, type='assertion', 
#                     end_time=datetime.now(), 
#                     passed=passed, 
#                     exception=exception,
#                     image=image
#                 )

#             i += 1    
#         await self.update_testcase(
#             time_completed=datetime.now()
#         )
#         await self.driver.close()
#         print('-- testcase run complete --')

#         if not self.testcase.passed and self.testcase.configs.get('create_issue'):
#             print('generating new Issue...')
#             Issuer(testcase=self.testcase).build_issue()

#         return None

    
    
    
    
    
    