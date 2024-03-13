import subprocess, json, uuid, boto3, \
shutil, os, requests, time
from ..models import Site, Scan
from scanerr import settings



class Yellowlab():

    """Initializes Yellow Lab Tools CLI and runs an audit of the site"""


    def __init__(self, scan=None, configs=None):
        self.scan = scan
        self.site = self.scan.site
        self.page = self.scan.page
        self.configs = configs

        # initial audits object
        self.audits = {
            "pageWeight": [], 
            "images": [], 
            "domComplexity": [], 
            "javascriptComplexity": [],
            "badJavascript": [],
            "jQuery": [],
            "cssComplexity": [],
            "badCSS": [],
            "fonts": [],
            "serverConfig": [],
        }
        
        # initial scores object
        self.scores = {
            "globalScore": None,
            "pageWeight": None, 
            "requests": None, 
            "domComplexity": None, 
            "javascriptComplexity": None,
            "badJavascript": None,
            "jQuery": None,
            "cssComplexity": None,
            "badCSS": None,
            "fonts": None,
            "serverConfig": None,
        }

    
    def yellowlab_cli(self):
        proc = subprocess.Popen([
                'yellowlabtools',
                self.page.page_url,
                f'--device={self.configs["device"]}'
                ], 
            stdout=subprocess.PIPE,
            user='app',
        )
        stdout_value = proc.communicate()[0]
        return stdout_value


    def yellowlab_api(self) -> dict:
        """ 
        Serves as the primary method for collecting YL metrics.
        Sends API requests to http://yellowlab:8383
        or localhost:8383

        Returns --> raw YL data
        """

        # defaults
        headers = {
            "content-type": "application/json",
        }
        data = {
            "url": self.page.page_url,
            "waitForResponse": True,
            "device": self.configs["device"]
        }

        # setting up initial request
        print('sending YLT API request...')
        res = requests.post(
            url=f'{settings.YELLOWLAB_ROOT}/api/runs',
            data=json.dumps(data),
            headers=headers
        ).json()

        print(res)

        # retrieve runId & pod_ip if present
        run_id = res['runId']
        pod_ip = res.get('pod_ip')

        NEW_ROOT = f'http://{pod_ip}:8383' if pod_ip != None else settings.YELLOWLAB_ROOT
        print(f'setting NEW_ROOT to -> {NEW_ROOT}')
        
        wait_time = 0
        max_wait = 1200
        done = False

        # waiting for run to complete
        while not done and wait_time < max_wait:

            # sending run request check
            print('checking YLT API request...')
            res = requests.get(
                url=f'{NEW_ROOT}/api/runs/{run_id}',
                headers=headers
            ).json()

            print(f'res -> {res}')

            # checking status
            status = res['run']['status']['statusCode']
            position = res['run']['status'].get('position')
            if status == 'awaiting':
                max_wait = (120 * position)
            if status == 'complete':
                done = True
            if status == 'failed':
                print('YELLOWLAB API FAILED')
                raise RuntimeError
                break

            # incrementing time
            time.sleep(5)
            wait_time += 5


        # getting run results
        print('retrieveing YLT API request...')
        res = requests.get(
            url=f'{NEW_ROOT}/api/results/{run_id}',
            headers=headers
        ).json()
    
        return res



    
    def process_data(self, stdout_json: dict) -> dict:
        """ 
        Accepts JSON data from either CLI or API method 
        and parses into usable Scanerr data.

        Expects the following:
            stdout_json: <dict> or json from output
            
        Returns --> formatted YL data <dict> 
        """

        # setup boto3 configurations
        s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # iterating through categories to get relevant yl_audits and store them in their respective `audits = {}` obj
        for cat in self.audits:
            cat_audits = stdout_json["scoreProfiles"]["generic"]["categories"][cat]["rules"]
            for a in cat_audits:
                try:
                    audit = stdout_json["rules"][a]
                    self.audits[cat].append(audit)
                except:
                    pass

        # get scores from each category
        for key in self.scores:
            if key != 'globalScore':
                self.scores[key] = stdout_json["scoreProfiles"]["generic"]["categories"][key]["categoryScore"]

        # adding globalScore
        self.scores['globalScore'] = stdout_json["scoreProfiles"]["generic"]["globalScore"]


        # self.scores['pageWeight'] = stdout_json["scoreProfiles"]["generic"]["categories"]["pageWeight"]["categoryScore"]
        # # self.scores['requests'] = stdout_json["scoreProfiles"]["generic"]["categories"]["requests"]["categoryScore"]
        # self.scores['images'] = stdout_json["scoreProfiles"]["generic"]["categories"]["images"]["categoryScore"]
        # self.scores['domComplexity'] = stdout_json["scoreProfiles"]["generic"]["categories"]["domComplexity"]["categoryScore"]
        # self.scores['javascriptComplexity'] = stdout_json["scoreProfiles"]["generic"]["categories"]["javascriptComplexity"]["categoryScore"]
        # self.scores['badJavascript'] = stdout_json["scoreProfiles"]["generic"]["categories"]["badJavascript"]["categoryScore"]
        # self.scores['jQuery'] = stdout_json["scoreProfiles"]["generic"]["categories"]["jQuery"]["categoryScore"]
        # self.scores['cssComplexity'] = stdout_json["scoreProfiles"]["generic"]["categories"]["cssComplexity"]["categoryScore"]
        # self.scores['badCSS'] = stdout_json["scoreProfiles"]["generic"]["categories"]["badCSS"]["categoryScore"]
        # self.scores['fonts'] = stdout_json["scoreProfiles"]["generic"]["categories"]["fonts"]["categoryScore"]
        # self.scores['serverConfig'] = stdout_json["scoreProfiles"]["generic"]["categories"]["serverConfig"]["categoryScore"]

        # save audits data as json file
        file_id = uuid.uuid4()
        with open(f'{file_id}.json', 'w') as fp:
            json.dump(audits, fp)
        
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

        data = {
            "scores": scores, 
            "audits": audits_url,
            "failed": False
        }

        # returning data 
        return data


    def get_data(self):

        scan_complete = False
        failed = False
        attempts = 0
        
        # trying yellowlab scan untill success or 2 attempts
        while not scan_complete and attempts >= 2:

            try:
                raw_data = self.yellowlab_cli()
                self.process_data(stdout_json=raw_data)

                # raw_data = self.yellowlab_api()
                # self.process_data(stdout_json=raw_data)

                scan_complete = True
                failed = False

            except Exception as e:
                print(f'YELLOWLAB API FAILED --> {e}')
                scan_complete = True
                failed = True
                attempts += 1

        data = {
            "scores": self.scores, 
            "audits": self.audits,
            "failed": failed
        }
            
        # returning final data
        return attempts