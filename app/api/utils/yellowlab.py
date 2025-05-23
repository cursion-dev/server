import subprocess, json, uuid, boto3, os, requests, time
from ..models import Site, Scan
from .devices import get_device
from cursion import settings






class Yellowlab():

    """
    Initializes Yellow Lab Tools CLI and runs an audit of the site

    Use self.get_data() to init a run
    """


    def __init__(self, scan=None):
        self.scan = scan
        self.site = self.scan.site
        self.page = self.scan.page
        self.configs = scan.configs
        self.audits_url = ''
        self.device_type = get_device(
            scan.configs['browser'], 
            scan.configs['device']
        )['type']

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
            "images": None, 
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
        """ 
        Serves as the CLI method for collecting YL metrics.
        Creates a sub process running yellowlabtools CLI

        Returns --> raw YL data (Dict)
        """

        print(f'starting YL with device type -> {self.device_type}')

        # initiating subprocess for YLT CLI
        proc = subprocess.Popen([
                'yellowlabtools',
                self.page.page_url,
                f'--device={self.device_type}'
                ], 
            stdout=subprocess.PIPE,
            user='app',
        )

        # retrieving data from process
        stdout_value = proc.communicate()[0]

        # converting stdout str into Dict
        stdout_json = json.loads(stdout_value)
        return stdout_json



    def yellowlab_api(self) -> dict:
        """ 
        Serves as the API method for collecting YL metrics.
        Sends API requests to http://yellowlab:8383
        or localhost:8383

        Returns --> raw YL data (Dict)
        """

        headers = {
            "Content-Type": "application/json",
            "Connection": "close"
        }
        payload = {
            "url": self.page.page_url,
            "waitForResponse": True,
            "device": self.device_type
        }

        def curl_post(url, data):
            cmd = [
                "curl", "-s", "-X", "POST",
                "-H", f"Content-Type: {headers['Content-Type']}",
                "-H", f"Connection: {headers['Connection']}",
                "--data", json.dumps(data),
                url
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return json.loads(result.stdout)

        def curl_get(url):
            cmd = [
                "curl", "-s", "-X", "GET",
                "-H", f"Connection: {headers['Connection']}",
                url
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return json.loads(result.stdout)

        # setting up initial request
        root = settings.YELLOWLAB_ROOT
        res = curl_post(f"{root}/api/runs", payload)

        # retrieve runId & pod_ip if present
        run_id = res["runId"]
        pod_ip = res.get("pod_ip")
        new_root = f"http://{pod_ip}:8383" if pod_ip else root

        wait_time = 0
        max_wait = 1200
        done = False
         
        # waiting for run to complete
        while not done and wait_time < max_wait:
            
            # sending run request check
            status_res = curl_get(f"{new_root}/api/runs/{run_id}")
            status = status_res["run"]["status"]["statusCode"]
            position = status_res["run"]["status"].get("position")

            # checking status
            if status == "awaiting" and position:
                max_wait = max(max_wait, 120 * position)
            elif status == "complete":
                done = True
            elif status == "failed":
                raise RuntimeError("YellowLab run failed")

            # incrementing time
            time.sleep(5)
            wait_time += 5

        # Step 3: Retrieve results
        result = curl_get(f"{new_root}/api/results/{run_id}")
        return result



    
    def process_data(self, stdout_json: dict) -> dict:
        """ 
        Accepts JSON data from either CLI or API method 
        and parses into usable Cursion data.

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

        # iterating through categories to get relevant yl_audits 
        # and store them in their respective `audits = {}` obj
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
            if key == 'globalScore':
                self.scores['globalScore'] = stdout_json["scoreProfiles"]["generic"]["globalScore"]
            else:
                self.scores[key] = stdout_json["scoreProfiles"]["generic"]["categories"][key]["categoryScore"]


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
        self.audits_url = audits_url

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
        
        # trying yellowlab scan until success or 2 attempts
        while not scan_complete and attempts < 2:

            try:
                # CLI on first attempt
                if attempts < 1:
                    raw_data = self.yellowlab_cli()
                    self.process_data(stdout_json=raw_data)
                
                # API after first attempt
                if attempts >= 1:
                    raw_data = self.yellowlab_api()
                    self.process_data(stdout_json=raw_data)

                scan_complete = True
                failed = False

            except Exception as e:
                print(f'YELLOWLAB FAILED (attempt {attempts}) --> {e}')
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