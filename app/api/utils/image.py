from .driver_s import driver_init, driver_wait, quit_driver
from .driver_p import driver_init as driver_init_p
from selenium import webdriver
from ..models import Site, Scan, Test, Mask
from selenium.webdriver.chrome.options import Options
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from sewar.full_ref import uqi, mse, ssim, msssim, psnr, ergas, vifp, rase, sam, scc
from skimage.metrics import structural_similarity
from scanerr import settings
from PIL import Image as I, ImageChops, ImageStat
from pyppeteer import launch
from datetime import datetime
from asgiref.sync import sync_to_async
import time, os, sys, json, uuid, boto3, \
    statistics, shutil, numpy, cv2





class Image():
    """
    High level Image handler used to compare screenshots of
    a website and retrieve single one-page screenshots. 
    Also known as VRT or Visual Regression Testing.
    Contains five methods scan(), scan_p(), test(), 
    screenshot(), and screenshot_p(). The _p appendage
    denotes using Puppeteer as the webdriver:

        def scan(site, driver=None) -> grabs multiple 
            screenshots of the website and uploads 
            them to s3.


        def test(test=<test:object>) -> compares each 
            screenshot in the two scans and records 
            a score out of 100%


        def screeshot(site, driver=None) -> grabs single 
            screenshot of the site and uploads it to s3

    """


    def __init__(self):
        
        # scripts
        self.set_jquery = (
            """
            var jq = document.createElement('script');
            jq.src = "https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js";
            document.getElementsByTagName('head')[0].appendChild(jq);
            """
        )




    def check_timeout(self, timeout, start_time):
        """
        Checks to see if the current time exceedes the alotted timeout. 
        
        returns -> True if timeout exceeded
        """

        current = datetime.now()
        diff = current - start_time
        if diff.total_seconds() >= timeout:
            print('exceeded timeout')
            return True
        else:
            return False






    def scan(self, scan, configs, driver=None,):
        """
        Grabs multiple screenshots of the website and uploads 
        them to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        site = scan.site
        page = scan.page

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init()
            driver_present = False


        # request page_url 
        driver.get(page.page_url)

        # waiting for network requests to resolve
        driver_wait(
            driver=driver, 
            interval=int(configs.get('interval', 5)),  
            min_wait_time=int(configs.get('min_wait_time', 10)),
            max_wait_time=int(configs.get('max_wait_time', 30)),
        )


        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                driver.execute_script("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')
                
            # inserting video pausing scripts
            try:
                driver.execute_script("const video = document.querySelectorAll('video').forEach(vid => vid.pause());")
            except:
                print('cannnot pause videos')

        # mask all listed ids        
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    driver.execute_script(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')

        
        # mask all Global mask ids that are active
        active_masks = Mask.objects.filter(active=True)
        if len(active_masks) != 0:
            for mask in active_masks:
                try:
                    driver.execute_script(f"document.getElementById('{mask.mask_id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via global mask id provided')


        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                # driver.execute_script("window.scrollBy(0, window.innerHeight);")
                driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(configs.get('interval', 5)),  
                    min_wait_time=int(configs.get('min_wait_time', 10)),
                    max_wait_time=int(configs.get('max_wait_time', 30)),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{page.id}/{scan.id}/{pic_id}.png'
                root_path = settings.AWS_S3_URL_PATH
                image_url = f'{root_path}/{remote_path}'
            
                # upload to s3
                with open(image, 'rb') as data:
                    s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                        remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                    )
                # remove local copy
                os.remove(image)

                # create image obj and add to list
                img_obj = {
                    "index": index,
                    "id": str(pic_id),
                    "url": image_url,
                    "path": remote_path,
                }

                image_array.append(img_obj)

                index += 1 
            
            else:
                bottom = True

        if not driver_present:
            quit_driver(driver)

        return image_array







    def scan_full(self, scan, configs, driver=None,):
        """
        Grabs multiple screenshots of the website and uploads 
        them to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        site = scan.site
        page = scan.page

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init()
            driver_present = False


        # request page_url 
        driver.get(page.page_url)

        # waiting for network requests to resolve
        driver_wait(
            driver=driver, 
            interval=int(configs.get('interval', 5)),  
            min_wait_time=int(configs.get('min_wait_time', 10)),
            max_wait_time=int(configs.get('max_wait_time', 30)),
        )

        # getting full_page_height
        full_page_height = driver.execute_script("return document.scrollingElement.scrollHeight;")
        sizes = configs.get('window_size', '1920,1080').split(',')
        driver.set_window_size(int(sizes[0]), int(full_page_height))


        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                driver.execute_script("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')
                
            # inserting video pausing scripts
            try:
                driver.execute_script("const video = document.querySelectorAll('video').forEach(vid => vid.pause());")
            except:
                print('cannnot pause videos')

        # mask all listed ids        
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    driver.execute_script(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')

        
        # mask all Global mask ids that are active
        active_masks = Mask.objects.filter(active=True)
        if len(active_masks) != 0:
            for mask in active_masks:
                try:
                    driver.execute_script(f"document.getElementById('{mask.mask_id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via global mask id provided')


        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                # driver.execute_script("window.scrollBy(0, window.innerHeight);")
                driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(configs.get('interval', 5)),  
                    min_wait_time=int(configs.get('min_wait_time', 10)),
                    max_wait_time=int(configs.get('max_wait_time', 30)),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{page.id}/{scan.id}/{pic_id}.png'
                root_path = settings.AWS_S3_URL_PATH
                image_url = f'{root_path}/{remote_path}'
            
                # upload to s3
                with open(image, 'rb') as data:
                    s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                        remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                    )
                # remove local copy
                os.remove(image)

                # create image obj and add to list
                img_obj = {
                    "index": index,
                    "id": str(pic_id),
                    "url": image_url,
                    "path": remote_path,
                }

                image_array.append(img_obj)

                index += 1 
            
            else:
                bottom = True

        if not driver_present:
            quit_driver(driver)

        return image_array







    def _scan(self, scan, configs, driver=None,):
        """
        Grabs multiple screenshots of the website and uploads 
        them to s3 as one package.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        site = scan.site
        page = scan.page

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init()
            driver_present = False


        # request page_url 
        driver.get(page.page_url)

        # waiting for network requests to resolve
        driver_wait(
            driver=driver, 
            interval=int(configs.get('interval', 5)),  
            min_wait_time=int(configs.get('min_wait_time', 10)),
            max_wait_time=int(configs.get('max_wait_time', 30)),
        )

        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                driver.execute_script("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')

            # inserting video pausing scripts
            try:
                driver.execute_script("const video = document.querySelectorAll('video').forEach(vid => vid.pause());")
            except:
                print('cannnot pause videos')
            

        # mask all listed ids        
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    driver.execute_script(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')

        
        # mask all Global mask ids that are active
        active_masks = Mask.objects.filter(active=True)
        if len(active_masks) != 0:
            for mask in active_masks:
                try:
                    driver.execute_script(f"document.getElementById('{mask.mask_id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via global mask id provided')

        
        # vertically concats two images
        def add_images(im1, im2):
            im1 = I.open(im1)
            im2 = I.open(im2)
            new_img = I.new('RGB', (im1.width, im1.height + im2.height))
            new_img.paste(im1, (0, 0))
            new_img.paste(im2, (0, im1.height))
            return new_img


        # scroll one frame at a time and capture screenshot
        final_img = None
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                # driver.execute_script("window.scrollBy(0, window.innerHeight);")
                driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(configs.get('interval', 5)),  
                    min_wait_time=int(configs.get('min_wait_time', 10)),
                    max_wait_time=int(configs.get('max_wait_time', 30)),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')

                # adding new image to bottom of existing image (if not index = 0)
                pic_id_2 = uuid.uuid4()
                if index != 0 and final_img is not None:
                    add_images(final_img, image).save(f'{pic_id_2}.png')
                    os.remove(final_img)
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                else:
                    I.open(image).save(f'{pic_id_2}.png')
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                
                # remove local copy
                os.remove(image)

                index += 1 
            
            else:
                bottom = True


        remote_path = f'static/sites/{site.id}/{page.id}/{scan.id}/{pic_id_2}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(final_img, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
       

        # create image obj and add to list
        img_obj = {
            "index": 0,
            "id": str(pic_id_2),
            "url": image_url,
            "path": remote_path,
        }

        image_array.append(img_obj)
        
        # remove local copy
        os.remove(final_img)

        if not driver_present:
            quit_driver(driver)

        return image_array






    async def scan_p(self, scan, configs):
        """
        Using Puppeteer, grabs multiple screenshots of the website and uploads 
        them to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        site = scan.site
        _page = scan.page

        driver = await driver_init_p(window_size=configs.get('window_size', '1920,1080'), wait_time=configs.get('max_wait_time', 30))
        page = await driver.newPage()

        sizes = configs.get('window_size', '1920,1080').split(',')
        is_mobile = False
        if configs.get('device') == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': configs.get('max_wait_time', 30)*1000
        }

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

        if configs.get('device') == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # requesting page_url
        await page.goto(_page.page_url, page_options)

        
        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                await page.evaluate("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')

            # pausing videos
            try:
                videos = await page.querySelectorAll('video')
                for vid in videos:
                    await page.evaluate('(vid) => vid.pause()', vid)
            except Exception as e:
                print(e)


        # mask all listed ids
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    await page.evaluate(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')


        # mask all Global mask ids that are active
        @sync_to_async
        def get_active_global_masks():
            masks = Mask.objects.filter(active=True)
            active_masks = []
            if len(masks) > 0:
                for mask in masks:
                    active_masks.append(mask.id)
            return active_masks

        active_masks = await get_active_global_masks()

        for mask in active_masks:
            try:
                await page.evaluate(f"document.getElementById('{mask}').style.visibility='hidden';")
                print('masked an element')
            except:
                print('cannot find element via global mask id provided')


        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                await page.evaluate("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = await page.evaluate("window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()

                # interact with and wait for page to load
                await page.mouse.move(0, 0)
                await page.mouse.move(0, 100)
                time.sleep(int(configs.get('min_wait_time', 10)))
                
            
                # get screenshot
                await page.screenshot({'path': f'{pic_id}.png'})

                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{_page.id}/{scan.id}/{pic_id}.png'
                root_path = settings.AWS_S3_URL_PATH
                image_url = f'{root_path}/{remote_path}'
            
                # upload to s3
                with open(image, 'rb') as data:
                    s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                        remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                    )
                # remove local copy
                os.remove(image)

                # create image obj and add to list
                img_obj = {
                    "index": index,
                    "id": str(pic_id),
                    "url": image_url,
                    "path": remote_path,
                }

                image_array.append(img_obj)

                index += 1 
            
            else:
                bottom = True

        
        await driver.close()

        return image_array






    async def scan_p_full(self, scan, configs):
        """
        Using Puppeteer, grabs multiple screenshots of the website and uploads 
        them to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        @sync_to_async
        def get_site():
            site = scan.site
            return site
        
        @sync_to_async
        def get_page():
            _page = scan.page
            return _page

        site = await get_site()
        _page = await get_page()

        driver = await driver_init_p(window_size=configs.get('window_size', '1920,1080'), wait_time=int(configs.get('max_wait_time', 30)))
        page = await driver.newPage()

        sizes = configs.get('window_size', '1920,1080').split(',')
        is_mobile = False
        if configs.get('device') == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': int(configs.get('max_wait_time', 30))*1000
        }

        # requesting page_url to get height of 
        await page.goto(_page.page_url, page_options)

        # getting full_page_height
        full_page_height = await page.evaluate("document.scrollingElement.scrollHeight;")

        viewport = {
            'width': int(sizes[0]),
            'height': int(full_page_height),
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

        if configs.get('device') == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # requesting page_url
        await page.goto(_page.page_url, page_options)

        
        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                await page.evaluate("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')

            # pausing videos
            try:
                videos = await page.querySelectorAll('video')
                for vid in videos:
                    await page.evaluate('(vid) => vid.pause()', vid)
            except Exception as e:
                print(e)


        # mask all listed ids
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    await page.evaluate(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')


        # mask all Global mask ids that are active
        @sync_to_async
        def get_active_global_masks():
            masks = Mask.objects.filter(active=True)
            active_masks = []
            if len(masks) > 0:
                for mask in masks:
                    active_masks.append(mask.id)
            return active_masks

        active_masks = await get_active_global_masks()

        for mask in active_masks:
            try:
                await page.evaluate(f"document.getElementById('{mask}').style.visibility='hidden';")
                print('masked an element')
            except:
                print('cannot find element via global mask id provided')


        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(int(configs.get('timeout', 300)), start_time):
                break

            # scroll single frame
            if index != 0:
                await page.evaluate("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = await page.evaluate("window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()

                # interact with and wait for page to load
                await page.mouse.move(0, 0)
                await page.mouse.move(0, 100)
                time.sleep(int(configs.get('min_wait_time', 10)))
                
            
                # get screenshot
                await page.screenshot({'path': f'{pic_id}.png'})

                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{_page.id}/{scan.id}/{pic_id}.png'
                root_path = settings.AWS_S3_URL_PATH
                image_url = f'{root_path}/{remote_path}'
            
                # upload to s3
                with open(image, 'rb') as data:
                    s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                        remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                    )
                # remove local copy
                os.remove(image)

                # create image obj and add to list
                img_obj = {
                    "index": index,
                    "id": str(pic_id),
                    "url": image_url,
                    "path": remote_path,
                }

                image_array.append(img_obj)

                index += 1 
            
            else:
                bottom = True

        
        await driver.close()

        return image_array










    async def _scan_p(self, scan, configs):
        """
        Using Puppeteer, grabs multiple screenshots of the website and uploads 
        them to s3 as a single image.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # get page and site objs
        site = scan.site
        _page = scan.page

        driver = await driver_init_p(window_size=configs.get('window_size', '1920,1080'), wait_time=configs.get('max_wait_time', 30))
        page = await driver.newPage()

        sizes = configs.get('window_size', '1920,1080').split(',')
        is_mobile = False
        if configs.get('device') == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': configs.get('max_wait_time', 30)*1000
        }

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

        if configs.get('device') == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # requesting page_url
        await page.goto(_page.page_url, page_options)

        if configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                await page.evaluate("const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');styleElement.appendChild(styleTagCSSes);document.head.appendChild(styleElement);")
            except:
                print('cannot pause animations')

            # pausing videos
            try:
                videos = await page.querySelectorAll('video')
                for vid in videos:
                    await page.evaluate('(vid) => vid.pause()', vid)
            except Exception as e:
                print(e)

        # mask all listed ids
        if configs.get('mask_ids') is not None and configs.get('mask_ids') != '':
            ids = configs.get('mask_ids').split(',')
            for id in ids:
                try:
                    await page.evaluate(f"document.getElementById('{id}').style.visibility='hidden';")
                    print('masked an element')
                except:
                    print('cannot find element via id provided')


        # mask all Global mask ids that are active
        @sync_to_async
        def get_active_global_masks():
            masks = Mask.objects.filter(active=True)
            active_masks = []
            for mask in masks:
                active_masks.append(mask.id)
            return active_masks

        active_masks = await get_active_global_masks()

        for mask in active_masks:
            try:
                await page.evaluate(f"document.getElementById('{mask}').style.visibility='hidden';")
                print('masked an element')
            except:
                print('cannot find element via global mask id provided')


        # vertically concats two images
        @sync_to_async
        def add_images(im1, im2):
            im1 = I.open(im1)
            im2 = I.open(im2)
            new_img = I.new('RGB', (im1.width, im1.height + im2.height))
            new_img.paste(im1, (0, 0))
            new_img.paste(im2, (0, im1.height))
            return new_img


        # scroll one frame at a time and capture screenshot
        final_img = None
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                await page.evaluate("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = await page.evaluate("window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()

                # interact with and wait for page to load
                await page.mouse.move(0, 0)
                await page.mouse.move(0, 100)
                time.sleep(int(configs.get('min_wait_time', 10)))
                
            
                # get screenshot
                await page.screenshot({'path': f'{pic_id}.png'})
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                
                # adding new image to bottom of existing image (if not index = 0)
                pic_id_2 = uuid.uuid4()
                if index != 0 and final_img is not None:
                    new_img = await add_images(final_img, image)
                    new_img.save(f'{pic_id_2}.png')
                    os.remove(final_img)
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                else:
                    I.open(image).save(f'{pic_id_2}.png')
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                
                # remove local copy
                os.remove(image)

                index += 1 
            
            else:
                bottom = True


        remote_path = f'static/sites/{site.id}/{_page.id}/{scan.id}/{pic_id_2}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(final_img, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
       

        # create image obj and add to list
        img_obj = {
            "index": 0,
            "id": str(pic_id_2),
            "url": image_url,
            "path": remote_path,
        }

        image_array.append(img_obj)
        
        # remove local copy
        os.remove(final_img)

        
        await driver.close()

        return image_array










    def test(self, test, index=None):
        """
        Compares each screenshot between the two scans and records 
        a score out of 100%.

        Compairsons used : 
            - Structral Similarity Index (ssim)
            - PIL ImageChop Differences, Ratio
            - cv2 ORB Brute-force Matcher, Ratio
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # setup temp dirs
        if not os.path.exists(os.path.join(settings.BASE_DIR, f'temp/{test.id}')):
            os.makedirs(os.path.join(settings.BASE_DIR, f'temp/{test.id}'))
        
        # temp root
        temp_root = os.path.join(settings.BASE_DIR, f'temp/{test.id}')
        
        # loop through and download each img in scan and compare it.
        pre_scan_images = test.pre_scan.images
        img_test_results = []
        scores = []
        i = 0

        if index is not None:
            pre_scan_images = [test.pre_scan.images[index]]
            i = index

        for pre_img_obj in pre_scan_images:
            
            # getting pre_scan image
            pre_img_path = os.path.join(temp_root, f'{pre_img_obj["id"]}.png')
            with open(pre_img_path, 'wb') as data:
                s3.download_fileobj(str(settings.AWS_STORAGE_BUCKET_NAME), pre_img_obj["path"], data)
            
            # getting post_scan image
            try:
                post_img_obj = test.post_scan.images[i]
            except:
                post_img_obj = None
            
            if post_img_obj is not None:
                post_img_path = os.path.join(temp_root, f'{post_img_obj["id"]}.png')
                with open(post_img_path, 'wb') as data:
                    s3.download_fileobj(str(settings.AWS_STORAGE_BUCKET_NAME), post_img_obj["path"], data)
                
                # open images with PIL Image library
                post_img = I.open(post_img_path)
                pre_img = I.open(pre_img_path)
                
                # check and reformat image sizes if necessary
                pre_img_w, pre_img_h = pre_img.size
                post_img_w, post_img_h = post_img.size

                # pre_img is longer
                if pre_img_h > post_img_h:
                    new_pre_img = pre_img.crop((0, 0, pre_img_w, post_img_h))
                    new_pre_img.save(pre_img_path, quality=100)
                    pre_img = I.open(pre_img_path)
                # post_img is longer
                if post_img_h > pre_img_h:
                    post_img = post_img.crop((0, 0, post_img_w, pre_img_h))
                    new_post_img.save(post_img_path, quality=100)
                    new_post_img = I.open(post_img_path)


                # build two new images with differences highlighted
                def highlight_diffs(pre_img_path, post_img_path, index):
                    '''
                        Returns -> two new images with highlights & float(ssim_score)
                    '''
                    # Load the images
                    image1 = cv2.imread(pre_img_path)
                    image2 = cv2.imread(post_img_path)

                    # Convert the images to grayscale
                    gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
                    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)

                    # Compute the SSIM map
                    (ssim_score, diff) = structural_similarity(gray1, gray2, full=True)

                    # Highlight the differences
                    diff = (diff * 255).astype("uint8")

                    # Threshold the difference map
                    _, thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

                    # Find contours of the differences
                    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    # Draw rectangles around the differences
                    for contour in contours:
                        (x, y, w, h) = cv2.boundingRect(contour)
                        cv2.rectangle(image1, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.rectangle(image2, (x, y), (x+w, y+h), (0, 255, 0), 2)

                    # Save the output images
                    img_1_id = uuid.uuid4()
                    img_2_id = uuid.uuid4()
                    cv2.imwrite(temp_root + f"/{img_1_id}.png", image1)
                    cv2.imwrite(temp_root + f"/{img_2_id}.png", image2)                    
                    img_objs = save_images(img_1_id, img_2_id, index)
                    
                    data = {
                        "img_objs": img_objs,
                        "ssim_score": ssim_score
                    }

                    return data


                # saving old images to new test.id path
                def save_images(pre_img_id, post_img_id, index):
                    image_ids = [pre_img_id, post_img_id]
                    img_objs = []
                    for img_id in image_ids:
                        image = os.path.join(temp_root, f'{img_id}.png')
                        remote_path = f'static/sites/{test.page.site.id}/{test.page.id}/{test.id}/{img_id}.png'
                        root_path = settings.AWS_S3_URL_PATH
                        image_url = f'{root_path}/{remote_path}'
                    
                        # upload to s3
                        with open(image, 'rb') as data:
                            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                            )
                        
                        # building img obj
                        obj = {
                            "id": str(img_id),
                            "url": image_url,
                            "path": remote_path,
                            "index": index,
                        }
                        img_objs.append(obj)
                        
                    return img_objs


                # test images with PIL
                def pil_score(pre_img, post_img):
                    try:
                        if (pre_img.mode != post_img.mode) \
                                or (pre_img.size != post_img.size) \
                                or (pre_img.getbands() != post_img.getbands()):
                            raise Exception('images are not comparable')

                        # Generate diff image in memory.
                        diff_img = ImageChops.difference(pre_img, post_img)

                        # Calculate difference as a ratio.
                        stat = ImageStat.Stat(diff_img)
                        diff_ratio = (sum(stat.mean) / (len(stat.mean) * 255)) * 100
                        pil_img_score = (100 - diff_ratio)
                        # print(f'PIL score -> {pil_img_score}')
                        return pil_img_score
                    
                    except Exception as e:
                        print(e)


                # test with cv2
                def cv2_score(pre_img, post_img):
                    try:
                        orb = cv2.ORB_create()

                        # convert to array
                        pre_img_array = numpy.array(pre_img)
                        post_img_array = numpy.array(post_img)

                        # detect keypoints and descriptors
                        kp_a, desc_a = orb.detectAndCompute(pre_img_array, None)
                        kp_b, desc_b = orb.detectAndCompute(post_img_array, None)

                        # define the bruteforce matcher object
                        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                            
                        # perform matches. 
                        matches = bf.match(desc_a, desc_b)

                        # Look for similar regions with distance < 20. (from 0 to 100)
                        similar_regions = [i for i in matches if i.distance < 20]  
                        if len(matches) == 0:
                            cv2_img_score = 100
                        else:
                            cv2_img_score = (len(similar_regions) / len(matches)) * 100
                            # print(f'cv2 -> {cv2_img_score}')
                            
                        return cv2_img_score

                    except Exception as e:
                        print(e)



                # test images
                try:
                    # generating new highlighted images and score via ssim
                    ssim_results = highlight_diffs(pre_img_path, post_img_path, i)
                    pre_img_diff = ssim_results['img_objs'][0]
                    post_img_diff = ssim_results['img_objs'][1]
                    
                    # img_score_tupple = ssim(pre_img_array, post_img_array)
                    # img_score_list = list(img_score_tupple)  statistics.fmean(img_score_list)
                    ssim_img_score =  ssim_results['ssim_score'] * 100

                    # pillow scoring
                    pil_img_score = pil_score(pre_img, post_img)
                    
                    # pixel perfect scoring
                    cv2_img_score = cv2_score(pre_img_array, post_img_array)

                    # weighted average
                    img_score = ((ssim_img_score * 2) + (pil_img_score * 1) + (cv2_img_score * 5)) / 8

                    # saving old images to test.id path
                    old_imgs = save_images(pre_img_obj['id'], post_img_obj['id'], i)
                    pre_img = old_imgs[0]
                    post_img = old_imgs[1]

                except Exception as e:
                    print(e)
                    img_score = None
                    pre_img = None
                    post_img = None
                    pre_img_diff = None
                    post_img_diff = None

                # create img test obj and add to array
                img_test_obj = {
                    "index": i, 
                    "pre_img": pre_img,
                    "post_img": post_img,
                    "pre_img_diff": pre_img_diff, 
                    "post_img_diff": post_img_diff, 
                    "score": img_score,
                }

                img_test_results.append(img_test_obj)
                scores.append(img_score)

            # remove local copies
            if post_img_obj is not None:
                try:
                    os.remove(post_img_path)
                except Exception as e:
                    print(e)
            try:        
                os.remove(pre_img_path)
            except Exception as e:
                print(e)

            i += 1

        # remove temp dir
        shutil.rmtree(temp_root)

        # averaging scores and storing in images_delta obj
        try:
            avg_score = statistics.fmean(scores)
        except:
            avg_score = None
            
        images_delta = {
            "average_score": avg_score,
            "images": img_test_results,
        }

        return images_delta











    def screenshot(self, site=None, url=None, configs=None, driver=None):
        """
        Grabs single screenshot of the website and uploads 
        it to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        if not configs:
            configs = {
                "interval": 5,
                "window_size": "1920,1080",
                "max_wait_time": 60,
                "min_wait_time": 10,
                "device": "desktop"
            }

        # initialize driver if not passed as param
        if not driver:
            driver = driver_init(window_size=configs.get('window_size', '1920,1080'), device=configs.get('device'))


        # get or create site data
        if site is None:
            site_id = uuid.uuid4()
            site_url = url
        else:
            site_id = site.id
            site_url = site.site_url
        
        # request site_url 
        driver.get(site_url)


        # wait for site to fully load
        driver_wait(
            driver=driver, 
            interval=int(configs.get('interval', 5)),  
            min_wait_time=int(configs.get('min_wait_time', 10)),
            max_wait_time=int(configs.get('max_wait_time', 30)),
        )

        # grab screenshot
        pic_id = uuid.uuid4()
        driver.save_screenshot(f'{pic_id}.png')
        image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
        remote_path = f'static/sites/{site_id}/{page.id}/{pic_id}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(image, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
        # remove local copy
        os.remove(image)

        # create image obj and add to list
        img_obj = {
            "id": str(pic_id),
            "url": image_url,
            "path": remote_path,
        }

        # quit driver
        quit_driver(driver)

        return img_obj



    async def screenshot_p(self, site=None, url=None, configs=None):
        """
        Using Puppeteer, grabs single screenshot of the website and uploads 
        it to s3.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        if not configs:
            configs = {
                "interval": 5,
                "driver": "puppeteer",
                "device": "desktop",
                "window_size": "1920,1080",
                "max_wait_time": 60,
                "min_wait_time": 10
            }

        driver = await driver_init_p(window_size=configs.get('window_size', '1920,1080'), wait_time=configs.get('max_wait_time', 30))
        page = await driver.newPage()

        sizes = configs.get('window_size', '1920,1080').split(',')
        is_mobile = False
        if configs.get('device') == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': configs.get('max_wait_time', 30)*1000
        }

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

        if configs.get('device') == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # get or create site data
        if site is None:
            site_id = uuid.uuid4()
            site_url = url
        else:
            site_id = site.id
            site_url = site.site_url
        
        # request site_url 
        await page.goto(site_url, page_options)

        # interact with and wait for page to load
        await page.mouse.move(0, 0)
        await page.mouse.move(0, 100)
        time.sleep(int(configs.get('min_wait_time', 10)))

        # get screenshot
        pic_id = uuid.uuid4()
        await page.screenshot({'path': f'{pic_id}.png'})
        await driver.close()
        image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
        remote_path = f'static/sites/{site_id}/{page.id}/{pic_id}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'

        # upload to s3
        with open(image, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
        # remove local copy
        os.remove(image)

        # create image obj and add to list
        img_obj = {
            "id": str(pic_id),
            "url": image_url,
            "path": remote_path,
        }

        return img_obj