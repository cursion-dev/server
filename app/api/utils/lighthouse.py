from pathlib import Path
from ..models import Site, Scan
from .devices import get_device
from cursion import settings
import subprocess, json, uuid, boto3, os, requests






class Lighthouse():

    """
    Initializes Google's Lighthouse CLI and runs an audit of the site

    Use self.get_data() to init a run
    """


    def __init__(self, scan=None):
        self.scan = scan
        self.site = self.scan.site
        self.page = self.scan.page
        self.configs = scan.configs
        self.sizes = scan.configs['window_size'].split(',')
        self.cpu_slowdown = 1
        self.scale_factor = 2
        self.audits_url = ''
        self.device = get_device(
            scan.configs['browser'], 
            scan.configs['device']
        )
        self.is_mobile = str(self.device['type'] == 'mobile' or self.device['type'] == 'tablet').lower()

        # device specific network speeds
        self.speed = {
            'mobile': {
                'download': 4000,
                'upload': 1000,
                'rttMs': 40
            },
            'tablet': {
                'download': 4000,
                'upload': 1000,
                'rttMs': 40
            },
            'desktop': {
                'download': 12000,
                'upload': 5500,
                'rttMs': 10
            }
        }

        # initial scores object
        self.scores = {
            "seo": None,
            "accessibility": None,
            "performance": None,
            "best_practices": None,
            # "pwa": None,
            "crux": None,
            "average": None
        }
        
        # initial audits object
        self.audits = {
            "seo": [],
            "accessibility": [],
            "performance": [],
            "best_practices": [],
            # "pwa": [],
            "crux": []
        }



    def create_configs(self):
    
        # custom Lighthouse config
        config_js = f"""
            module.exports = {{
                extends: 'lighthouse:default',
                plugins: ['lighthouse-plugin-crux'],
                settings: {{
                    cruxToken: "{settings.GOOGLE_CRUX_KEY}",
                    skipAudits: [
                        "full-page-screenshot"
                    ],
                    screenEmulation: {{
                        mobile: {self.is_mobile},
                        width: {self.sizes[0]},
                        height: {self.sizes[1]},
                        deviceScaleFactor: {self.scale_factor},
                        disabled: false
                    }},
                    throttling: {{
                        cpuSlowdownMultiplier: {self.cpu_slowdown}
                    }},
                    emulatedUserAgent: {json.dumps(self.device['user_agent'])}
                }}
            }};
        """

        # define output path
        config_path = Path("api/utils/configs/custom-config.js")
        config_path.write_text(config_js)
        
        # return path for use in subprocess
        return config_path.as_posix()  



    
    def lighthouse_cli(self):
        """ 
        Serves as the CLI method for collecting LH metrics.
        Creates a sub process running lighthouse CLI

        Returns --> raw LH data (Dict)
        """

        # warm up the page by curl'ing site
        try:
            subprocess.run(
                ['curl', '-sS', '--max-time', '5', self.page.page_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except subprocess.CalledProcessError:
            pass

        # initiating subprocess for LH CLI
        proc = subprocess.Popen([
                'lighthouse', 
                f'--config-path=api/utils/configs/default-config.js',
                '--quiet',
                self.page.page_url, 
                '--plugins=lighthouse-plugin-crux',
                '--extra-headers=api/utils/configs/extra-headers.json',
                f'--chrome-flags=--no-sandbox --headless --disable-dev-shm-usage', 
                f'--form-factor={self.device["type"]}',
                f'--screenEmulation.width={self.sizes[0]}',
                f'--screenEmulation.height={self.sizes[1]}',
                f'--screenEmulation.mobile={self.is_mobile}',
                f'--emulatedUserAgent={self.device["user_agent"]}',
                f'--throttling.cpuSlowdownMultiplier={self.cpu_slowdown}',
                f'--throttling.downloadThroughputKbps={self.speed[self.device["type"]]["download"]}',
                f'--throttling.uploadThroughputKbps={self.speed[self.device["type"]]["upload"]}',
                f'--throttling.rttMs={self.speed[self.device["type"]]["rttMs"]}',
                f'--throttling-method=devtools',
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
        try:
            delm = '{\n  "lighthouseVersion"'
            stdout_string = delm + stdout_string.split(delm)[1]
        except Exception as e:
            print(e)
            
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
            "strategy": self.device['type'],
            "key": settings.GOOGLE_CRUX_KEY
        }

        # cats
        cats = 'category=ACCESSIBILITY&category=BEST_PRACTICES&category=PERFORMANCE&category=SEO'

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
        and parses into usable Cursion data.

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

        # changing audits & score names before iterations
        self.scores['best-practices'] = self.scores.pop('best_practices')
        self.audits['best-practices'] = self.audits.pop('best_practices')
        self.audits['lighthouse-plugin-crux'] = self.audits.pop('crux')

        # allow_list of 0 weighted audits
        allow_list = [
            'server-response-time', 'cache-insight',
            'interactive',
        ]

        # iterating through categories to get relevant lh_audits 
        # and store them in their respective `audits = {}` obj
        for cat in self.audits:
            # skipping non-existent cat
            if stdout_json["categories"].get(cat) is None:
                continue
            cat_audits = stdout_json["categories"].get(cat).get("auditRefs")
            if cat_audits is not None:
                for a in cat_audits:
                    if int(a["weight"]) > 0 or a["id"] in allow_list:
                        audit = stdout_json["audits"][a["id"]]
                        self.audits[cat].append(audit)
       
        # get scores from each category
        score_queue = [] 
        for cat in self.scores:
            # skipping non-existent cat
            if stdout_json["categories"].get(cat) is None:
                continue
            # record score
            self.scores[cat] = round(stdout_json["categories"][cat]["score"] * 100)
            # add to queue
            score_queue.append(self.scores[cat])

        # changing audits & score names back to original
        self.scores['best_practices'] = self.scores.pop('best-practices')
        self.audits['best_practices'] = self.audits.pop('best-practices')
        self.audits['crux'] = self.audits.pop('lighthouse-plugin-crux')

        # dynamically calculating average
        average_score = round(sum(score_queue)/len(score_queue))
        self.scores['average'] = average_score


        # save audits data as json file
        file_id = uuid.uuid4()
        with open(f'{file_id}.json', 'w') as fp:
            json.dump(self.audits, fp)
        
        # upload to s3 and return url
        audit_file = os.path.join(settings.BASE_DIR, f'{file_id}.json')
        remote_path = f'static/sites/{self.site.id}/{self.page.id}/{self.scan.id}/{file_id}.json'
        root_path = settings.AWS_S3_URL_PATH
        self.audits_url = f'{root_path}/{remote_path}'
    
        # upload to s3
        with open(audit_file, 'rb') as data:
            s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "application/json"}
            )
        # remove local copy
        os.remove(audit_file)

        data = {
            "scores": self.scores, 
            "audits": self.audits_url,
            "failed": False
        }

        # returning data 
        return data


    
    def get_data(self):

        scan_complete = False
        failed = True
        attempts = 0

        # trying lighthouse scan untill success or 2 attempts
        while not scan_complete and attempts < 2:

            try:
                # CLI on first attempt if not API Priority
                if attempts < 1 and not self.configs.get('api_priority'):
                    raw_data = self.lighthouse_cli()
                    self.process_data(stdout_json=raw_data)
                
                # API after first attempt or if API Priority
                if attempts >= 1 or self.configs.get('api_priority'):
                    raw_data = self.lighthouse_api()
                    self.process_data(stdout_json=raw_data)

                scan_complete = True
                failed = False

            except Exception as e:
                print(f'LIGHTHOUSE FAILED (attempt {attempts}) --> {e}')
                scan_complete = False
                failed = True
                attempts += 1

        data = {
            "scores": self.scores, 
            "audits": self.audits_url if self.audits_url != '' else None,
            "failed": failed
        }
            
        # returning final data
        return data
