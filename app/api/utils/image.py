from .driver_s import driver_init, driver_wait
from .driver_p import driver_init as driver_init_p
from selenium import webdriver
from ..models import Site, Scan, Test
from selenium.webdriver.chrome.options import Options
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from sewar.full_ref import uqi, mse, ssim
from scanerr import settings
from PIL import Image as I
from pyppeteer import launch
import time, os, sys, json, uuid, boto3, \
    statistics, shutil, numpy





class Image():
    """
    High level Image handler used to compare screenshots of
    a website. Also known as VRT or Visual Regression Testing.
    Contains two methods scan() and test():

        def scan(site, driver=None) -> grabs multiple 
            screenshots of the website and uploads 
            them to s3.


        def test(test=<test:object>) -> compares each 
            screenshot in the two scans and records 
            a score out of 100%


        def screeshot(site, driver=None) -> grabs single 
            screenshot of the site and uploads it to s3

    """



    def scan(self, site, configs, driver=None,):
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

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init()
            driver_present = False


        # request site_url 
        driver.get(site.site_url)

        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        while not bottom:

            # scroll single frame
            if index != 0:
                driver.execute_script("window.scrollBy(0, window.innerHeight);")

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + window.innerHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(configs['interval']),  
                    min_wait_time=int(configs['min_wait_time']),
                    max_wait_time=int(configs['max_wait_time']),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{pic_id}.png'
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
            driver.quit()

        return image_array



    async def scan_p(self, site, configs):
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

        driver = await driver_init_p(window_size=configs['window_size'], wait_time=configs['max_wait_time'])
        page = await driver.newPage()

        sizes = configs['window_size'].split(',')
        is_mobile = False
        if configs['device'] == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': configs['max_wait_time']*1000
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

        if configs['device'] == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # requesting site url
        await page.goto(site.site_url, page_options)

        # scroll one frame at a time and capture screenshot
        image_array = []
        index = 0
        last_height = -1
        bottom = False
        while not bottom:

            # scroll single frame
            if index != 0:
                await page.evaluate("window.scrollBy(0, window.innerHeight);")

            # get current position and compare to previous
            new_height = await page.evaluate("window.pageYOffset + window.innerHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()

                # interact with and wait for page to load
                await page.mouse.move(0, 0)
                await page.mouse.move(0, 100)
                time.sleep(configs['min_wait_time'])
                
            
                # get screenshot
                await page.screenshot({'path': f'{pic_id}.png'})
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                remote_path = f'static/sites/{site.id}/{pic_id}.png'
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





    def test(self, test, index=None):
        """
        compares each screenshot between the two scans and records 
        a score out of 100%.
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # setup temp files
        if not os.path.exists(os.path.join(settings.BASE_DIR, f'temp/{test.site.id}')):
            os.makedirs(os.path.join(settings.BASE_DIR, f'temp/{test.site.id}'))
        
        # temp root
        temp_root = os.path.join(settings.BASE_DIR, f'temp/{test.site.id}')
        
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
            
            # open with PIL Image library
            pre_img = I.open(pre_img_path)
            # convert to array
            pre_img_array = numpy.array(pre_img)

            # getting post_scan image
            try:
                post_img_obj = test.post_scan.images[i]
            except:
                post_img_obj = None
            
            if post_img_obj is not None:
                post_img_path = os.path.join(temp_root, f'{post_img_obj["id"]}.png')
                with open(post_img_path, 'wb') as data:
                    s3.download_fileobj(str(settings.AWS_STORAGE_BUCKET_NAME), post_img_obj["path"], data)
                
                # open with PIL Image library
                post_img = I.open(post_img_path)
                # convert to array
                post_img_array = numpy.array(post_img)

                # test images
                try:
                    img_score_tupple = ssim(pre_img_array, post_img_array)
                    img_score_list = list(img_score_tupple)
                    img_score = statistics.fmean(img_score_list) * 100
                except Exception as e:
                    print(e)
                    img_score = None

                # create img test obj and add to array
                img_test_obj = {
                    "index": i, 
                    "pre_img": pre_img_obj,
                    "post_img": post_img_obj,
                    "score": img_score,
                }

                img_test_results.append(img_test_obj)
                scores.append(img_score)

            # remove local copies
            if post_img_obj is not None:
                os.remove(post_img_path)
            os.remove(pre_img_path)

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
            driver = driver_init(window_size=configs['window_size'], device=configs['device'])


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
            interval=int(configs['interval']),  
            min_wait_time=int(configs['min_wait_time']),
            max_wait_time=int(configs['max_wait_time']),
        )

        # grab screenshot
        pic_id = uuid.uuid4()
        driver.save_screenshot(f'{pic_id}.png')
        image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
        remote_path = f'static/sites/{site_id}/{pic_id}.png'
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

        driver = await driver_init_p(window_size=configs['window_size'], wait_time=configs['max_wait_time'])
        page = await driver.newPage()

        sizes = configs['window_size'].split(',')
        is_mobile = False
        if configs['device'] == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': configs['max_wait_time']*1000
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

        if configs['device'] == 'mobile':
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
        time.sleep(configs['min_wait_time'])

        # get screenshot
        pic_id = uuid.uuid4()
        await page.screenshot({'path': f'{pic_id}.png'})
        await driver.close()
        image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
        remote_path = f'static/sites/{site_id}/{pic_id}.png'
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