from .driver import driver_init, driver_wait
from selenium import webdriver
from ..models import Site, Scan, Test
from selenium.webdriver.chrome.options import Options
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from sewar.full_ref import uqi, mse, ssim
from scanerr import settings
from PIL import Image as I
import time, os, sys, json, uuid, boto3, statistics, shutil, numpy




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

    """



    def scan(self, site, driver=None):
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
                driver_wait(driver=driver, interval=5, max_wait_time=30)

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







    def test(self, test):
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
        img_test_results = []
        scores = []
        i = 0
        for pre_img_obj in test.pre_scan.images:
            
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
                img_score_tupple = ssim(pre_img_array, post_img_array)
                img_score_list = list(img_score_tupple)
                img_score = statistics.fmean(img_score_list) * 100

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
        avg_score = statistics.fmean(scores)
        images_delta = {
            "average_diff": avg_score,
            "images": img_test_results,
        }

        return images_delta
