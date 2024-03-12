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

    
    def init_audit(self):
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
        Serves as the backup method for collecting YL metrics.
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

        NEW_ROOT = f'http://{pod_ip}:8383' if pod_ip else settings.YELLOWLAB_ROOT
        
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

            # checking status
            status = res['status']['statusCode']
            position = res['status'].get('position')
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

        # initial audits object
        audits = {
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

        # iterating through categories to get relevant yl_audits and store them in their respective `audits = {}` obj
        for cat in audits:
            cat_audits = stdout_json["scoreProfiles"]["generic"]["categories"][cat]["rules"]
            for a in cat_audits:
                try:
                    audit = stdout_json["rules"][a]
                    audits[cat].append(audit)
                except:
                    pass

        # get scores from each category
        globalScore = stdout_json["scoreProfiles"]["generic"]["globalScore"]
        pageWeight_score = stdout_json["scoreProfiles"]["generic"]["categories"]["pageWeight"]["categoryScore"]
        # requests_score = stdout_json["scoreProfiles"]["generic"]["categories"]["requests"]["categoryScore"]
        images_score = stdout_json["scoreProfiles"]["generic"]["categories"]["images"]["categoryScore"]
        domComplexity_score = stdout_json["scoreProfiles"]["generic"]["categories"]["domComplexity"]["categoryScore"]
        javascriptComplexity_score = stdout_json["scoreProfiles"]["generic"]["categories"]["javascriptComplexity"]["categoryScore"]
        badJavascript_score = stdout_json["scoreProfiles"]["generic"]["categories"]["badJavascript"]["categoryScore"]
        jQuery_score = stdout_json["scoreProfiles"]["generic"]["categories"]["jQuery"]["categoryScore"]
        cssComplexity_score = stdout_json["scoreProfiles"]["generic"]["categories"]["cssComplexity"]["categoryScore"]
        badCSS_score = stdout_json["scoreProfiles"]["generic"]["categories"]["badCSS"]["categoryScore"]
        fonts_score = stdout_json["scoreProfiles"]["generic"]["categories"]["fonts"]["categoryScore"]
        serverConfig_score = stdout_json["scoreProfiles"]["generic"]["categories"]["serverConfig"]["categoryScore"]

        scores = {
            "globalScore": globalScore,
            "pageWeight": pageWeight_score, 
            # "requests": requests_score,
            "images": images_score,  
            "domComplexity": domComplexity_score, 
            "javascriptComplexity": javascriptComplexity_score,
            "badJavascript": badJavascript_score,
            "jQuery": jQuery_score,
            "cssComplexity": cssComplexity_score,
            "badCSS": badCSS_score,
            "fonts": fonts_score,
            "serverConfig": serverConfig_score,
        }

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
        
        # try CLI method first
        # try:
        #     stdout_value = self.init_audit() 
        #     # decode bytes into string
        #     stdout_string = stdout_value.decode('iso-8859-1')
        
        #     if len(stdout_string) != 0:
        #         if 'Runtime error encountered' in stdout_string:
        #             error = {'error': 'yellowlab ran into a problem',}
        #             return error

        #         # convert to dict
        #         stdout_json = json.loads(stdout_value)
        #         data = self.process_data(stdout_json=stdout_json)
        #         return data
                
        #     else:
        #         raise RuntimeError
        
        # try API method if CLI fails
        # except Exception as e:
            # print(e)

        try:
            raw_data = self.yellowlab_api()
            data = self.process_data(stdout_json=raw_data)
            return data

        except Exception as e:
            print(f'YELLOWLAB API FAILED --> {e}')

            scores = {
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

            audits = {
                "pageWeight": [], 
                "requests": [], 
                "domComplexity": [], 
                "javascriptComplexity": [],
                "badJavascript": [],
                "jQuery": [],
                "cssComplexity": [],
                "badCSS": [],
                "fonts": [],
                "serverConfig": [],
            }

            data = {
                "scores": scores, 
                "audits": audits,
                "failed": True
            }
        
            return data
        

