from .driver_p import driver_init
import time, asyncio, uuid, json
from ..models import * 
from datetime import datetime
from asgiref.sync import sync_to_async





class Caser():


    def __init__(self, testcase):
        self.testcase = testcase
        self.site_url = self.testcase.site.site_url
        self.steps = self.testcase.steps
        self.case_name = self.testcase.case.name
        self.configs = self.testcase.configs



    @sync_to_async
    def update_testcase(
            self, index=None, type=None, start_time=None, end_time=None, 
            passed=None, exception=None, time_completed=None,
        ):
        if start_time != None:
            self.testcase.steps[index][type]['time_created'] = str(start_time)
        if end_time != None:
            self.testcase.steps[index][type]['time_completed'] = str(end_time)
        if passed != None:
            self.testcase.steps[index][type]['passed'] = passed
        if exception != None:
            self.testcase.steps[index][type]['exception'] = str(exception)
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

    @sync_to_async
    def format_element(self, element):
        elememt = json.dumps(element).rstrip('"').lstrip('"')
        return element

    
    
    
    async def run(self):


        print(f'beginging testcase for {self.site_url}  \
            using case {self.case_name}')
        
        # initate driver
        self.driver = await driver_init()
        
        # init page obj 
        self.page = await self.driver.newPage()

        # setting up page with configs
        sizes = self.configs['window_size'].split(',')
        is_mobile = False
        if self.configs['device'] == 'mobile':
            is_mobile = True
        
        self.page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': int(self.configs['max_wait_time'])*1000
        }

        print(f'setting max timeout to -> {int(self.configs["max_wait_time"])}s')

        viewport = {
            'width': int(sizes[0]),
            'height': int(sizes[1]),
            'isMobile': is_mobile,
        }
        
        userAgent = (
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/99.0.4812.0 Mobile Safari/537.36"
        )
        
        emulate_options = {
            'viewport': viewport,
            'userAgent': userAgent
        }

        if self.configs['device'] == 'mobile':
            await self.page.emulate(emulate_options)
        else:
            await self.page.setViewport(viewport)


        i = 0
        for step in self.steps:
            print(f'-- running step #{i+1} --')
            # print(f'step contents: {step}')

            if step['action']['type'] == 'navigate':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )

                try:
                    print(f'navigating to {self.site_url}{step["action"]["path"]}')
                    # using puppeteer, navigate to requested path & wait for page to load
                    await self.page.goto(f'{self.site_url}{step["action"]["path"]}', self.page_options)
                    time.sleep(int(self.configs['min_wait_time']))

                except Exception as e:
                    exception = e
                    passed = False

                
                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                )
                    


            if step['action']['type'] == 'click':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )

                try:
                    print(f'clicking element -> {step["action"]["element"]}')
                    # using puppeteer, find and click on the 'element' 
                    selector = await self.format_element(step["action"]["element"])
                    await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
                    # scrolling to element 
                    await self.page.evaluate(f'document.querySelector({selector}).scrollIntoView()')
                    element = await self.page.J(selector)
                    await element.click()
                    time.sleep(int(self.configs['min_wait_time']))
                
                except Exception as e:
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                ) 


            if step['action']['type'] == 'change':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )
                
                try:
                    print(f'changing element to value -> {step["action"]["value"]}') 
                    # using puppeteer, find and click on the 'element'
                    if step["action"]["element"] != (None or ''):
                        selector = await self.format_element(step["action"]["element"])
                        await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
                        # scrolling to element 
                        await self.page.evaluate(f'document.querySelector({selector}).scrollIntoView()')
                        element = await self.page.J(selector)
                        await element.click(clickCount=3)
                    await self.page.keyboard.type(step["action"]["value"])
                    time.sleep(int(self.configs['min_wait_time']))
                
                except Exception as e:
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                ) 

            
            if step['action']['type'] == 'keyDown':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='action', 
                    start_time=datetime.now()
                )
                
                try:
                    print(f'keyDown action for key -> {step["action"]["key"]}')
                    # using puppeteer, press the selected key
                    await self.page.keyboard.press(step['action']['key'])
                    time.sleep(int(self.configs['min_wait_time']))
                
                except Exception as e:
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                )
            



            if step['assertion']['type'] == 'match':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='assertion', 
                    start_time=datetime.now()
                )

                try:
                    print(f'asserting that element value -> {step["assertion"]["element"]} matches {step["assertion"]["value"]}')
                    # using puppeteer, find elememt and assert if element.text == assertion.text
                    selector = await self.format_element(step["assertion"]["element"])
                    await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
                    # scrolling to element 
                    await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
                    elementText = await self.page.evaluate(f'document.querySelector("{selector}").textContent')
                    elementText = elementText.strip()
                    print(f'elementText => {elementText}')
                    print(f'value => {step["assertion"]["value"]}')
                    assert elementText == step["assertion"]["value"]

                except Exception as e:
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                )

            
            if step['assertion']['type'] == 'exists':
                exception = None
                passed = True
                await self.update_testcase(
                    index=i, type='assertion', 
                    start_time=datetime.now()
                )

                try:
                    print(f'asserting that element -> {step["assertion"]["element"]} exists')
                    # using puppeteer, find elememt and assert it exists
                    selector = await self.format_element(step["assertion"]["element"])
                    await self.page.waitForSelector(selector, timeout=(int(self.configs['max_wait_time'])*1000))
                    await self.page.J(selector)

                except Exception as e:
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception
                )

            i += 1    
        await self.update_testcase(
            time_completed=datetime.now()
        )
        await self.driver.close()
        print('-- testcase run complete --')