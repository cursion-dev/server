from .driver_p import driver_init
import time, asyncio, uuid, json, boto3, os
from ..models import * 
from datetime import datetime
from asgiref.sync import sync_to_async
from scanerr import settings





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
            passed=None, exception=None, time_completed=None, image=None,
        ):
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

    @sync_to_async
    def format_element(self, element):
        elememt = json.dumps(element).rstrip('"').lstrip('"')
        return str(element)



    
    async def save_screenshot(self, page):
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
        await page.screenshot({'path': f'{pic_id}.png'})

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
        return  image_url

    
    
    
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


            # adding catch if nav is not first
            if i == 0 and step['action']['type'] != 'navigate':
                print(f'navigating to {self.site_url} before first step')
                # using puppeteer, navigate to site root path & wait for page to load
                await self.page.goto(f'{self.site_url}', self.page_options)
                time.sleep(int(self.configs['min_wait_time']))



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
                    image = await self.save_screenshot(page=self.page)

                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                
                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
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
                    # scrolling to element using plain JavaScript
                    await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
                    element = await self.page.J(selector)
                    await element.click()
                    time.sleep(int(self.configs['min_wait_time']))
                    image = await self.save_screenshot(page=self.page)
                
                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
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
                        # scrolling to element using plain JavaScript 
                        await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
                        element = await self.page.J(selector)
                        await element.click(clickCount=3)
                    await self.page.keyboard.type(step["action"]["value"])
                    time.sleep(int(self.configs['min_wait_time']))
                    image = await self.save_screenshot(page=self.page)
                
                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
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
                    image = await self.save_screenshot(page=self.page)
                
                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='action', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
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
                    # scrolling to element using plain JavaScript
                    await self.page.evaluate(f'document.querySelector("{selector}").scrollIntoView()')
                    elementText = await self.page.evaluate(f'document.querySelector("{selector}").textContent')
                    elementText = elementText.strip()
                    print(f'elementText => {elementText}')
                    print(f'value => {step["assertion"]["value"]}')
                    assert elementText == step["assertion"]["value"]
                    image = await self.save_screenshot(page=self.page)

                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
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
                    image = await self.save_screenshot(page=self.page)

                except Exception as e:
                    image = await self.save_screenshot(page=self.page)
                    exception = e
                    passed = False

                await self.update_testcase(
                    index=i, type='assertion', 
                    end_time=datetime.now(), 
                    passed=passed, 
                    exception=exception,
                    image=image
                )

            i += 1    
        await self.update_testcase(
            time_completed=datetime.now()
        )
        await self.driver.close()
        print('-- testcase run complete --')