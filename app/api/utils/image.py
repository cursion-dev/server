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
    Contains three methods scan_s(), scan_p(), test(). 
    The _p appendage denotes using Puppeteer as the webdriver
    and the _s appendage denotes using Selenium as the webdriver:

        def scan_s(driver=None) -> using selenium
            grabs multiple screenshots of the website 
            and uploads them to s3.

        def scan_p() -> using puppeteer
            grabs multiple screenshots of the website 
            and uploads them to s3.

        def test(test=<test:object>) -> compares each 
            screenshot in the two scans and records 
            a score out of 100%

    """


    def __init__(self, scan, configs):

        # main scan object
        self.scan = scan

        # main configs object
        self.configs = configs
        
        # main image_array for scans
        self.image_array = []
        
        # setup boto3 configurations
        self.s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # scripts
        self.pause_video_script = (
            "const video = document.querySelectorAll('video').forEach(vid => vid.pause());"
        )

        self.set_jquery = (
            """
            var jq = document.createElement('script');
            jq.src = "https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js";
            document.getElementsByTagName('head')[0].appendChild(jq);
            """
        )

        self.pause_animations_script = (
            """
            const styleElement = document.createElement('style');styleElement.setAttribute('id','style-tag');
            const styleTagCSSes = document.createTextNode('*,:after,:before{-webkit-transition:none!important;-moz-transition:none!important;-ms-transition:none!important;-o-transition:none!important;transition:none!important;-webkit-transform:none!important;-moz-transform:none!important;-ms-transform:none!important;-o-transform:none!important;-webkit-animation:none!important;animation:none!important;transform:none!important;transition-delay:0s!important;transition-duration:0s!important;animation-delay:-0.0001s!important;animation-duration:0s!important;animation-play-state:paused!important;caret-color:transparent!important;color-adjust:exact!important;}');
            styleElement.appendChild(styleTagCSSes);
            document.head.appendChild(styleElement);
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




    def add_images(self, im1, im2):
        """
        Joins img1 and im2 vertically and saves as "new_img"
        
        Returns -> new_img <Image>
        """
        im1 = I.open(im1)
        im2 = I.open(im2)
        new_img = I.new('RGB', (im1.width, im1.height + im2.height))
        new_img.paste(im1, (0, 0))
        new_img.paste(im2, (0, im1.height))
        return new_img
        


    
    def save_image(self, pic_id, image):
        """
        Upload image to s3, save info as image_obj,
        add image_obj to image_array, & remove image file
        """
        remote_path = f'static/sites/{self.scan.site.id}/{self.scan.page.id}/{self.scan.id}/{pic_id}.png'
        root_path = settings.AWS_S3_URL_PATH
        image_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(image, 'rb') as data:
            self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
            )
    
        # create image obj and add to list
        img_obj = {
            "index": 0,
            "id": str(pic_id),
            "url": image_url,
            "path": remote_path,
        }
        self.image_array.append(img_obj)

        print(f'adding {img_obj["url"]} to image_array')
        
        # remove local copy
        os.remove(image)








    def scan_s(self, driver=None):
        """
        Grabs full length screenshots of the website and uploads 
        them to s3.
        """

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init()
            driver_present = False

        # request page_url 
        driver.get(self.scan.page.page_url)

        # waiting for network requests to resolve
        driver_wait(
            driver=driver, 
            interval=int(self.configs.get('interval', 5)),  
            min_wait_time=int(self.configs.get('min_wait_time', 10)),
            max_wait_time=int(self.configs.get('max_wait_time', 30)),
        )

        # defining browser demesions
        sizes = self.configs.get('window_size', '1920,1080').split(',')

        # getting full_page_height
        if self.configs.get('auto_height', True):
            full_page_height = driver.execute_script("return document.scrollingElement.scrollHeight;")
            sizes = self.configs.get('window_size', '1920,1080').split(',')
            driver.set_window_size(int(sizes[0]), int(full_page_height))


        if self.configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                driver.execute_script(self.pause_animations_script)
            except:
                print('cannot pause animations')
                
            # inserting video pausing scripts
            try:
                driver.execute_script(self.pause_video_script)
            except:
                print('cannnot pause videos')

        # mask all listed ids        
        if self.configs.get('mask_ids') is not None and self.configs.get('mask_ids') != '':
            ids = self.configs.get('mask_ids').split(',')
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
        final_img = None
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(self.configs.get('timeout', 300), start_time):
                break

            # scroll single frame
            if index != 0:
                driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(self.configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(self.configs.get('interval', 5)),  
                    min_wait_time=int(self.configs.get('min_wait_time', 10)),
                    max_wait_time=int(self.configs.get('max_wait_time', 30)),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')

                # resizing image to remove duplicate portions
                img = I.open(image)
                width, height = img.size
                left = 0
                top = height - (height_diff/2)
                right = width
                _bottom = height
                new_img = img.crop((left, top, right, _bottom))
                new_img.save(image, quality=100)
                            
                # adding new image to bottom of existing image (if not index = 0)
                pic_id_2 = uuid.uuid4()
                if index != 0 and final_img is not None:
                    self.add_images(final_img, image).save(f'{pic_id_2}.png')
                    os.remove(final_img)
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                else:
                    I.open(image).save(f'{pic_id_2}.png')
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                
                os.remove(image)
                index += 1 
            
            else:
                bottom = True

        # saving image
        self.save_image(pic_id=pic_id_2, image=final_img)

        if not driver_present:
            quit_driver(driver)

        return self.image_array








    async def scan_p(self):
        """
        Using Puppeteer, grabs full length screenshots of the website and uploads 
        them to s3.
        """

        @sync_to_async
        def get_page():
            _page = self.scan.page
            return _page

        _page = await get_page()

        driver = await driver_init_p(
            window_size=self.configs.get('window_size', '1920,1080'), 
            wait_time=int(self.configs.get('max_wait_time', 30))
        )
        page = await driver.newPage()

        sizes = self.configs.get('window_size', '1920,1080').split(',')
        is_mobile = False
        if self.configs.get('device') == 'mobile':
            is_mobile = True
        
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': int(self.configs.get('max_wait_time', 30))*1000
        }

        # requesting page_url to get height of 
        await page.goto(_page.page_url, page_options)

        # getting full page_height
        page_height = int(sizes[1])
        if self.configs.get('auto_height', True):
            page_height = await page.evaluate("document.scrollingElement.scrollHeight;")

        viewport = {
            'width': int(sizes[0]),
            'height': int(page_height),
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

        if self.configs.get('device') == 'mobile':
            await page.emulate(emulate_options)
        else:
            await page.setViewport(viewport)

        # requesting page_url
        await page.goto(_page.page_url, page_options)

        if self.configs.get('disable_animations') == True:
            # inserting animation pausing script
            try:
                await page.evaluate(self.pause_animations_script)
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
        if self.configs.get('mask_ids') is not None and self.configs.get('mask_ids') != '':
            ids = self.configs.get('mask_ids').split(',')
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
    
        @sync_to_async
        def save_image(*args, **kwargs):
            self.save_image(pic_id=pic_id, image=final_img)

        # scroll one frame at a time and capture screenshot
        final_img = None
        index = 0
        last_height = -1
        bottom = False
        start_time = datetime.now()
        while not bottom:

            # checking if maxed out time
            if self.check_timeout(int(self.configs.get('timeout', 300)), start_time):
                break

            # scroll single frame
            if index != 0:
                await page.evaluate("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(self.configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = await page.evaluate("window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()

                # interact with and wait for page to load
                await page.mouse.move(0, 0)
                await page.mouse.move(0, 100)
                time.sleep(int(self.configs.get('min_wait_time', 10)))
            
                # get screenshot
                await page.screenshot({'path': f'{pic_id}.png'})
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')
                
                # resizing image to remove duplicate portions
                img = I.open(image)
                width, height = img.size
                left = 0
                top = height - (height_diff)
                right = width
                _bottom = height
                new_img = img.crop((left, top, right, _bottom))
                new_img.save(image, quality=100)
                
                # adding new image to bottom of existing image (if not index = 0)
                pic_id_2 = uuid.uuid4()
                if index != 0 and final_img is not None:
                    self.add_images(final_img, image).save(f'{pic_id_2}.png')
                    os.remove(final_img)
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                else:
                    I.open(image).save(f'{pic_id_2}.png')
                    final_img = os.path.join(settings.BASE_DIR, f'{pic_id_2}.png')
                
                os.remove(image)
                index += 1 
            
            else:
                bottom = True
        
        # saving image
        await save_image(pic_id=pic_id, image=final_img)

        await driver.close()

        return self.image_array










    def test(self, test, index=None):
        """
        Compares each screenshot between the two scans and records 
        a score out of 100%.

        Compairsons used : 
            - Structral Similarity Index (ssim)
            - PIL ImageChop Differences, Ratio
            - cv2 ORB Brute-force Matcher, Ratio
        """

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

        # catching user error when scan_type 
        # did not include 'vrt'
        if pre_scan_images is None:
            images_delta = {
                "average_score": None,
                "images": None,
            }
            return images_delta


        for pre_img_obj in pre_scan_images:
            
            # getting pre_scan image
            pre_img_path = os.path.join(temp_root, f'{pre_img_obj["id"]}.png')
            with open(pre_img_path, 'wb') as data:
                self.s3.download_fileobj(str(settings.AWS_STORAGE_BUCKET_NAME), pre_img_obj["path"], data)
            
            # getting post_scan image
            try:
                post_img_obj = test.post_scan.images[i]
            except:
                post_img_obj = None
            
            if post_img_obj is not None:
                post_img_path = os.path.join(temp_root, f'{post_img_obj["id"]}.png')
                with open(post_img_path, 'wb') as data:
                    self.s3.download_fileobj(str(settings.AWS_STORAGE_BUCKET_NAME), post_img_obj["path"], data)
                
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
                    new_post_img = post_img.crop((0, 0, post_img_w, pre_img_h))
                    new_post_img.save(post_img_path, quality=100)
                    post_img = I.open(post_img_path)


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
                            self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
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
                    cv2_img_score = cv2_score(pre_img, post_img)

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





