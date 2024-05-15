import subprocess, json, uuid, boto3, shutil, os, requests
from ..models import Site, Scan
from scanerr import settings



class Lighthouse():

    """Initializes Google's Lighthouse CLI and runs an audit of the site"""


    def __init__(self, scan=None, configs=None):
        self.scan = scan
        self.site = self.scan.site
        self.page = self.scan.page
        self.configs = configs
        self.sizes = configs['window_size'].split(',')

        # initial scores object
        self.scores = {
            "seo": None,
            "accessibility": None,
            "performance": None,
            "best-practices": None,
            "pwa": None,
            "crux": None,
            "average": None
        }
        
        # initial audits object
        self.audits = {
            "seo": [],
            "accessibility": [],
            "performance": [],
            "best-practices": [],
            "pwa": [],
            "crux": []
        }

    
    def lighthouse_cli(self):
        """ 
        Serves as the CLI method for collecting LH metrics.
        Creates a sub process running lighthouse CLI

        Returns --> raw LH data (Dict)
        """

        # initiating subprocess for LH CLI
        proc = subprocess.Popen([
                'lighthouse', 
                '--config-path=api/utils/custom-config.js',
                '--quiet',
                self.page.page_url, 
                '--plugins=lighthouse-plugin-crux',
                '--chrome-flags="--no-sandbox --headless --disable-dev-shm-usage"', 
                f'--screenEmulation.width={self.sizes[0]}',
                f'--screenEmulation.height={self.sizes[1]}',
                f'--screenEmulation.{self.configs["device"]}',
                '--output',
                'json', 
            ], 
            stdout=subprocess.PIPE,
            user='app',
        )

        # retrieving data from process
        stdout_value = proc.communicate()[0]
        
        # decode bytes into string
        stdout_string = stdout_value.decode('iso-8859-1')

        # clean string of any errors
        delm = '{\n  "lighthouseVersion"'
        stdout_string = delm + stdout_string.split(delm)[1]

        # encode back to bytes
        stdout_value = stdout_string.encode('iso-8859-1')
        
        # converting stdout str into Dict
        stdout_json = json.loads(stdout_value)
        return stdout_json




    def lighthouse_api(self) -> dict:
        """ 
        Serves as the API method for collecting LH metrics.
        Sends API requests to 

        Returns --> raw LH data (Dict)
        """

        # defaults
        headers = {
            "content-type": "application/json",
        }
        params = {
            "url": self.page.page_url,
            "strategy": self.configs["device"],
            "key": settings.GOOGLE_CRUX_KEY
        }

        # cats
        cats = 'category=ACCESSIBILITY&category=BEST_PRACTICES&category=PERFORMANCE&category=PWA&category=SEO'

        # setting up initial request
        res = requests.get(
            url=f'{settings.LIGHTHOUSE_ROOT}?{cats}',
            params=params,
            headers=headers
        ).json()

        # try to get just LH response
        res = res.get('lighthouseResult')

        # return response
        return res



    def process_data(self, stdout_json: dict) -> dict:
        """ 
        Accepts JSON data from either CLI or API method 
        and parses into usable Scanerr data.

        Expects the following:
            stdout_json: <dict> or json from output
            
        Returns --> formatted LH data <dict> 
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # iterating through categories to get relevant lh_audits 
        # and store them in their respective `audits = {}` obj
        for cat in self.audits:
            # skipping non-existent cat
            if stdout_json["categories"].get(cat) is None:
                continue
            cat_audits = stdout_json["categories"].get(cat).get("auditRefs")
            if cat_audits is not None:
                for a in cat_audits:
                    if int(a["weight"]) > 0:
                        audit = stdout_json["audits"][a["id"]]
                        self.audits[cat].append(audit)
       
        # get scores from each category
        for key in self.scores:
            self.scores[key] = round(stdout_json["categories"][key]["score"])

        # changing audits & score names
        self.scores['best_practices'] = self.scores.pop('best-practices')
        self.audits['best_practices'] = self.audits.pop('best-practices')
        self.audits['crux'] = self.audits.pop('lighthouse-plugin-crux')
       
        
        # attempting crux
        try:
            crux_score = round(stdout_json["categories"]["lighthouse-plugin-crux"]["score"] * 100)
        except:
            crux_score = 0

        # dynamically calculating average
        if crux_score == 0 :
            crux_score = None
            average_score = round((
                    seo_score + accessibility_score + performance_score 
                    + best_practices_score + pwa_score
                )/ 5)
        else:
            average_score = round((
                    seo_score + accessibility_score + performance_score 
                    + best_practices_score + pwa_score + crux_score
                )/ 6)

        # save audits data as json file
        file_id = uuid.uuid4()
        with open(f'{file_id}.json', 'w') as fp:
            json.dump(self.audits, fp)
        
        # upload to s3 and return url
        audit_file = os.path.join(settings.BASE_DIR, f'{file_id}.json')
        remote_path = f'static/sites/{self.site.id}/{self.page.id}/{self.scan.id}/{file_id}.json'
        root_path = settings.AWS_S3_URL_PATH
        audits_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(audit_file, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "application/json"}
            )
        # remove local copy
        os.remove(audit_file)

        # updating opjects
        self.audits = audits_url

        data = {
            "scores": self.scores, 
            "audits": self.audits,
            "failed": False
        }

        # returning data 
        return data


    
    def get_data(self):

        scan_complete = False
        failed = None
        attempts = 0
        
        # trying lighthouse scan untill success or 2 attempts
        while not scan_complete and attempts < 2:

            raw_data = self.lighthouse_api()
            self.process_data(stdout_json=raw_data)

            # try:
            #     # CLI on first attempt
            #     if attempts < 1:
            #         # raw_data = self.lighthouse_cli()
            #         raw_data = self.lighthouse_api()
            #         self.process_data(stdout_json=raw_data)
                
            #     # API after first attempt
            #     if attempts >= 1:
            #         raw_data = self.lighthouse_api()
            #         self.process_data(stdout_json=raw_data)

            #     scan_complete = True
            #     failed = False

            # except Exception as e:
            #     print(f'LIGHTHOUSE FAILED (attempt {attempts}) --> {e}')
            #     scan_complete = False
            #     failed = True
            #     attempts += 1

        data = {
            "scores": self.scores, 
            "audits": self.audits,
            "failed": failed
        }
            
        # returning final data
        return data
