from .driver import driver_init, driver_wait, quit_driver
from ..models import Site, Scan, Test, Mask
from skimage.metrics import structural_similarity
from cursion import settings
from PIL import Image as I, ImageChops, ImageStat
from datetime import datetime
from asgiref.sync import sync_to_async
from openai import OpenAI
from pydantic import BaseModel
from .meter import meter_account
import time, os, sys, json, uuid, boto3, \
    statistics, shutil, numpy, cv2, requests






class Imager():
    """
    High level Image handler used to compare screenshots 
    of a website.

    Also known as VRT or Visual Regression Testing.
    Contains three methods scan_vrt(), test_vrt(), 
    & caserun_vrt():

        def scan_vrt(driver=None) -> using selenium
            grabs screenshots of the website 
            and uploads them to s3.

        def test_vrt() -> compares each 
            screenshot in the Test

        def caserun_vrt() -> compares the 
            screenshot in each step of a CaseRun
    """




    def __init__(
            self, 
            scan    : object=None, 
            test    : object=None,
            caserun : object=None
        ):

        # primary objects
        self.scan       = scan
        self.test       = test
        self.caserun    = caserun
        
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
            """
            document.querySelectorAll('video').forEach(vid => vid.pause());
            document.querySelectorAll('video').forEach(vid => vid.currentTime=0);
            """ 
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




    def check_timeout(self, timeout: int, start_time: str) -> bool:
        """
        Checks to see if the current time exceedes the alotted timeout. 
        
        Returns -> True if timeout exceeded
        """
        current = datetime.now()
        diff = current - start_time
        if diff.total_seconds() >= int(timeout):
            print('exceeded timeout')
            return True
        else:
            return False




    def add_images(self, im1: object, im2: object) -> object:
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
        


    
    def save_image(self, pic_id: str, image: object) -> None:
        """
        Upload image to s3, save info as image_obj,
        add image_obj to image_array, & remove image file

        Returns -> None
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

        return None




    def save_images(
            self, 
            pre_img_id: id=None, 
            post_img_id: id=None, 
            index: int=0
        ) -> dict:
        """ 
        Saves two images to test.id path in S3 bucket

        Expects: {
            pre_img_id  : uuid,
            post_img_id : uuid,
            index       : int, 
        }

        Returns: img_objs <list>
        """

        # build paths based test
        if self.test:
            remote_root = f'static/sites/{self.test.page.site.id}/{self.test.page.id}/{self.test.id}/'
            temp_root = os.path.join(settings.BASE_DIR, f'temp/{self.test.id}')
        
        # build paths based caserun
        if self.caserun:
            remote_root = f'static/caseruns/{self.caserun.id}/'
            temp_root = os.path.join(settings.BASE_DIR, f'temp/{self.caserun.id}')

        image_ids = [pre_img_id, post_img_id]
        img_objs = []
        for img_id in image_ids:
            image = os.path.join(temp_root, f'{img_id}.png')
            remote_path = f'{remote_root}{img_id}.png'
            root_path = settings.AWS_S3_URL_PATH
            image_url = f'{root_path}/{remote_path}'
        
            # upload to s3
            with open(image, 'rb') as data:
                self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                    remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "image/png"}
                )
            
            # building img obj
            img_objs.append({
                "id": str(img_id),
                "url": image_url,
                "path": remote_path,
                "index": index,
            })
            
        return img_objs




    def download_image(
            self, 
            url: str=None, 
            temp_root: str=None
        ) -> dict:
        """ 
        Parses image info and downloads image to local temp_root

        Expects: {
            'url'       : str, image url,
            'temp_root' : str, local temp dir
        }

        Returns: {
            'name'          : str, image name,
            'id'            : str, image id,
            'remote_path'   : str, remote path,
            'local_path'    : str, local path
        }
        """
        image_name = url.split('/')[-1]
        image_id = image_name.split('.')[0]
        remote_path = f'static{url.split('static')[1]}'
        local_path = os.path.join(temp_root, image_name)

        with open(local_path, 'wb') as data:
            self.s3.download_fileobj(
                settings.AWS_STORAGE_BUCKET_NAME, 
                remote_path, 
                data
            )

        # return data
        return {
            'name': image_name,
            'id': image_id,
            'remote_path': remote_path,
            'local_path': local_path
        }




    def highlight_diffs(
            self, 
            temp_root: str=None,
            pre_img_path: str=None, 
            post_img_path: str=None, 
            index: int=None
        ) -> dict:
        """
        Runs SSIM comparision and highlights 
        differences between two passed images

        Expects: {
            temp_root     : str,
            pre_img_path  : str,
            post_img_path : str,
            index         : int,
        }

        Returns: {
            'img_objs'   : dict,
            'ssim_score' : float
        }
        """
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
        img_objs = self.save_images(img_1_id, img_2_id, index)
        
        data = {
            "img_objs": img_objs,
            "ssim_score": ssim_score
        }

        return data




    def pil_score(
            self, 
            pre_img: object=None, 
            post_img: object=None
        ) -> float:
        """ 
        Runs pixel ratio comparison on the two 
        passed images and returns a score.

        Expects: {
            pre_img  : object,
            post_img : object,
        }

        Returns: pil_img_score <float>
        """
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



    
    def cv2_score(
            self, 
            pre_img: object=None, 
            post_img: object=None
        ) -> float:
        """ 
        Runs cv2 ORB Brute-force comparison on the two 
        passed images and returns a score.

        Expects: {
            pre_img  : object,
            post_img : object,
        }

        Returns: cv2_img_score <float>
        """
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




    def ai_compare(
            self, 
            pre_img_url: str=None, 
            post_img_url: str=None,
            score: float=None,
            highlighted: bool=False
        ) -> dict:
        """ 
        Using OpenAI, compares the two images and 
        provides a summary and boolean for 'broken'

        Expects: {
            pre_img_url     : str,
            post_img_url    : str,
            score           : float
        }

        Returns: {
            'summary': str,
            'broken': bool
        }
        """

        # define output as object (JSON)
        class Result(BaseModel):
            summary: str
            broken: bool

        # init client
        gpt_client = OpenAI(api_key=settings.GPT_API_KEY,)


        marked_up_images = str(
            "I've added green boxes arround the areas that have changed between the two images. \
            The green boxes may not be present if there are no changes. \
            Omit any reference to the green boxes in your response." 
        )
        
        # send request
        response = gpt_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Attached are two screenshots of the same website. \
                            I've calculated the Visual Regression SSIM score to be {score}% similar. \
                            Please perform a Visual Regression Analysis of the two images. \
                            {marked_up_images if highlighted else ''} \
                            Respond with a few sentance summary about what has changed. \
                            Look for changes in pictures, buttons, forms, vertial shifts, etc. \
                            Respond also with a boolean that is TRUE if the page should be considered broken. \
                            Consider any emerging portions that appear to be unrendered HTML a breaking change. \
                            If the same text is present in both images, then DO NOT consider it a 'breaking change'. \
                            Only consider 'breaking changes' on the second image. \
                            DO NOT consider new or altered text to be a 'breaking change'. \
                            DO NOT consider text changes within images or pictures on the webpage. \
                            DO NOT consider minor shifts (only a few pixels) to be a 'breaking change'. \
                            Ignore portions that appear to be advertizements. \
                            Please be somewhat strict with the analysis. \
                            Format response as a JSON object with 'summary': <string>, 'broken': <bool>"         
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": pre_img_url,
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": post_img_url,
                            },
                        },
                    ],
                }
            ],
            response_format=Result
        )

        try:
            result = response.choices[0].message.parsed
            result = {
                'summary': result.summary, 
                'broken': result.broken
            }
        except:
            result = {
                'summary': None, 
                'broken': None
            }

        # meter account if necessary
        if self.test.page.account.type == 'cloud' and self.test.page.account.cust_id:
            meter_account(str(self.test.page.account.id), 1)

        print(result)
        return result




    def scan_vrt(self, driver: object=None) -> list:
        """
        Grabs full length screenshots of the website and uploads 
        them to s3.

        Expects: {
            'driver': object
        }

        Returns -> self.image_array list
        """

        # initialize driver if not passed as param
        driver_present = True
        if not driver:
            driver = driver_init(
                browser=self.scan.configs.get('browser', 'chrome'),
                window_size=self.scan.configs.get('window_size', '1920,1080'),
                device=self.scan.configs.get('device', 'desktop'),
            )
            driver_present = False

        # request page_url 
        driver.get(self.scan.page.page_url)

        # waiting for network requests to resolve
        driver_wait(
            driver=driver, 
            interval=int(self.scan.configs.get('interval', 5)),  
            min_wait_time=int(self.scan.configs.get('min_wait_time', 10)),
            max_wait_time=int(self.scan.configs.get('max_wait_time', 30)),
        )

        # defining browser demesions
        sizes = self.scan.configs.get('window_size', '1920,1080').split(',')

        # calculating and auto setting page height
        if self.scan.configs.get('auto_height', True):

            # get scroll_height, client_height & set window_size
            scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")
            client_height = driver.execute_script("return document.documentElement.clientHeight;")

            # trying to match "document.body.clientHeight" 
            # and "document.body.scrollHeight"
            # iterate 3 times or untill height_diff is less than 20
            i = 0
            success = False
            while not success and i < 4:

                # set window_size
                driver.set_window_size(int(sizes[0]), (int(scroll_height)))
                
                # scroll down and up
                driver.execute_script(f"window.scrollBy(0, {client_height});")
                time.sleep(1)
                driver.execute_script(f"window.scrollBy(0, -{client_height});")
                
                # get client & new scroll height
                client_height = driver.execute_script("return document.documentElement.clientHeight;")
                new_scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")

                # get difference between full page height and new scrolled position
                height_diff = int(new_scroll_height) - int(client_height)

                # re-set window size
                print(f'adding {height_diff} to full_page_height')
                scroll_height += height_diff if height_diff > 0 else 0

                # checking difference
                if height_diff < 20:
                    success = True

                # increment
                i += 1


        if self.scan.configs.get('disable_animations') == True:
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
        if self.scan.configs.get('mask_ids') is not None and self.scan.configs.get('mask_ids') != '':
            ids = self.scan.configs.get('mask_ids').split(',')
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
            if self.check_timeout(self.scan.configs.get('timeout', 300), start_time):
                break

            # scroll single frame if not first frame and not auto_height
            if index != 0:
                driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight);")
                time.sleep(int(self.scan.configs.get('min_wait_time', 10)))

            # get current position and compare to previous
            new_height = driver.execute_script("return window.pageYOffset + document.documentElement.clientHeight")
            height_diff = new_height - last_height
            print(f'new_height => {new_height} | height_diff => {height_diff}')

            if height_diff > 20:
                last_height = new_height
                pic_id = uuid.uuid4()
                
                # waiting for network requests to resolve
                driver_wait(
                    driver=driver, 
                    interval=int(self.scan.configs.get('interval', 5)),  
                    min_wait_time=int(self.scan.configs.get('min_wait_time', 10)),
                    max_wait_time=int(self.scan.configs.get('max_wait_time', 30)),
                )

                # get screenshot
                driver.save_screenshot(f'{pic_id}.png')
                image = os.path.join(settings.BASE_DIR, f'{pic_id}.png')

                # resizing image to remove duplicate portions
                if index != 0:
                    img = I.open(image)
                    width, height = img.size
                    left = 0
                    top = height - ((height_diff/2)) # divide by 2 for "driver.scale_factor" 
                    right = width
                    botm = height
                    new_img = img.crop((left, top, right, botm))
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

        # clean up
        if not driver_present:
            quit_driver(driver)

        # return images
        return self.image_array




    def test_vrt(self) -> dict:
        """
        Compares each screenshot between the two scans and records 
        a score out of 100%.

        Compairsons used : 
            - Structral Similarity Index (ssim)
            - PIL ImageChop Differences, Ratio
            - cv2 ORB Brute-force Matcher, Ratio

        Expects: None

        Returns -> data: {
            'average_score' : float(0-100),
            'images'        : dict,
        }
        """

        # defaults
        i               = 0
        img_score       = None
        pre_img         = None
        post_img        = None
        pre_img_diff    = None
        post_img_diff   = None
        ai_summary      = None
        broken          = None
        images_delta    = {
            "average_score": None,
            "images": None,
        }

        # setup temp dirs
        if not os.path.exists(os.path.join(settings.BASE_DIR, f'temp/{self.test.id}')):
            os.makedirs(os.path.join(settings.BASE_DIR, f'temp/{self.test.id}'))
        
        # temp root
        temp_root = os.path.join(settings.BASE_DIR, f'temp/{self.test.id}')
    
        # catching user error
        if self.test.pre_scan.images is None or self.test.post_scan.images is None:
            shutil.rmtree(temp_root)
            return images_delta

        # download images
        pre_img_info = self.download_image(self.test.pre_scan.images[0].get('url'), temp_root)
        post_img_info = self.download_image(self.test.post_scan.images[0].get('url'), temp_root)

        # open images with PIL Image library
        pre_img = I.open(pre_img_info.get('local_path'))
        post_img = I.open(post_img_info.get('local_path'))
        
        # check and reformat image sizes if necessary
        pre_img_w, pre_img_h = pre_img.size
        post_img_w, post_img_h = post_img.size

        # pre_img is longer
        if pre_img_h > post_img_h:
            print(f'pre_img is larger, adjusting...')
            new_pre_img = pre_img.crop((0, 0, pre_img_w, post_img_h)).convert(mode=post_img.mode)
            new_pre_img.save(pre_img_info.get('local_path'), quality=100)
            pre_img = I.open(pre_img_info.get('local_path'))
        # post_img is longer
        if post_img_h > pre_img_h:
            print(f'post_img is larger, adjusting...')
            new_post_img = post_img.crop((0, 0, post_img_w, pre_img_h)).convert(mode=pre_img.mode)
            new_post_img.save(post_img_info.get('local_path'), quality=100)
            post_img = I.open(post_img_info.get('local_path'))

        # test images
        try:
            # generating new highlighted images and score via ssim
            ssim_results = self.highlight_diffs(
                temp_root, 
                pre_img_info.get('local_path'), 
                post_img_info.get('local_path'), 
                i
            )
            pre_img_diff = ssim_results['img_objs'][0]
            post_img_diff = ssim_results['img_objs'][1]
            
            # ssim scoring
            ssim_img_score =  ssim_results['ssim_score'] * 100

            # pillow scoring
            pil_img_score = self.pil_score(pre_img, post_img)
            
            # pixel perfect scoring
            cv2_img_score = self.cv2_score(pre_img, post_img)

            # weighted average
            img_score = ((ssim_img_score * 2) + (pil_img_score * 1) + (cv2_img_score * 5)) / 8

            # saving old images to test.id path
            old_imgs = self.save_images(pre_img_info.get('id'), post_img_info.get('id'), i)
            pre_img = old_imgs[0]
            post_img = old_imgs[1]

            # running AI comparison
            if self.test.post_scan.configs.get('ai_analysis') == True:
                resp = self.ai_compare(
                    pre_img_url   = self.test.pre_scan.images[0].get('url'), 
                    post_img_url  = self.test.post_scan.images[0].get('url'), 
                    score         = ssim_img_score,
                    highlighted   = False
                )
                ai_summary = resp.get('summary')
                broken = resp.get('broken')

        except Exception as e:
            print(e)

        # create img test obj and add to array
        img_test_obj = [{
            "index": 0, 
            "pre_img"       : pre_img,
            "post_img"      : post_img,
            "pre_img_diff"  : pre_img_diff, 
            "post_img_diff" : post_img_diff, 
            "score"         : img_score,
        }]

        # remove temp dir
        shutil.rmtree(temp_root)

        # formatting response
        images_delta = {
            "average_score" : img_score,
            "images"        : img_test_obj,
            "ai_summary"    : ai_summary,
            "broken"        : broken
        }

        # returning response
        return images_delta




    def caserun_vrt(self, step: int=None, type: str=None) -> dict:
        """
        Compares the passed step.screenshot to the case.step.screenshot
        and records a score out of 100%.

        Compairsons used : 
            - Structral Similarity Index (ssim)
            - PIL ImageChop Differences, Ratio
            - cv2 ORB Brute-force Matcher, Ratio

        Expects: {
            step : int, current step to test
            type : str, "action" or "assertion"
        }

        Returns: {
            'average_score' : float(0-100),
            'images'        : dict,
        }
        """

        # default 
        images_delta = {
            "average_score": None,
            "images": [{
                "index": step, 
                "pre_img": None,
                "post_img": None,
                "pre_img_diff": None, 
                "post_img_diff": None, 
                "score": None,
            }],
        }

        # setup temp dirs
        if not os.path.exists(os.path.join(settings.BASE_DIR, f'temp/{self.caserun.id}')):
            os.makedirs(os.path.join(settings.BASE_DIR, f'temp/{self.caserun.id}'))
        
        # temp root
        temp_root = os.path.join(settings.BASE_DIR, f'temp/{self.caserun.id}')
        
        # get image urls
        case_image_url = requests.get(self.caserun.case.steps['url']).json()[step][type].get('image')
        caserun_image_url = self.caserun.steps[step][type].get('image')

        # catch null urls and return early
        if case_image_url is None or caserun_image_url is None:
            shutil.rmtree(temp_root)
            return images_delta

        # download images
        case_img_info = self.download_image(case_image_url, temp_root)
        caserun_img_info = self.download_image(caserun_image_url, temp_root)

        # open images with PIL Image library
        pre_img = I.open(case_img_info.get('local_path'))
        post_img = I.open(caserun_img_info.get('local_path'))

        # test images
        try:
            # generating new highlighted images and score via ssim
            ssim_results = self.highlight_diffs(
                temp_root, 
                case_img_info.get('local_path'), 
                caserun_img_info.get('local_path'), 
                step
            )
            pre_img_diff = ssim_results['img_objs'][0]
            post_img_diff = ssim_results['img_objs'][1]
            
            # ssim scoring
            ssim_img_score =  ssim_results['ssim_score'] * 100

            # pillow scoring
            pil_img_score = self.pil_score(pre_img, post_img)
            
            # pixel perfect scoring
            cv2_img_score = self.cv2_score(pre_img, post_img)

            # weighted average
            img_score = ((ssim_img_score * 2) + (pil_img_score * 1) + (cv2_img_score * 5)) / 8

            # saving old images to caserun.id path
            old_imgs = self.save_images(case_img_info.get('id'), caserun_img_info.get('id'), step)
            pre_img = old_imgs[0]
            post_img = old_imgs[1]

        except Exception as e:
            print(e)
            img_score = None
            pre_img = None
            post_img = None
            pre_img_diff = None
            post_img_diff = None

        # create img obj and add to array
        img_obj = [{
            "index": step, 
            "pre_img": pre_img,
            "post_img": post_img,
            "pre_img_diff": pre_img_diff, 
            "post_img_diff": post_img_diff, 
            "score": img_score,
        }]

        # remove temp dir
        shutil.rmtree(temp_root)

        # formatting response
        images_delta = {
            "average_score": img_score,
            "images": img_obj,
        }

        # returning response
        return images_delta






