import subprocess, json
from ..models import Site, Scan



class Lighthouse():

    """Initializes Google's Lighthouse CLI and runs an audit of the site"""


    def __init__(self, site=None, configs=None):
        self.site = site
        self.configs = configs
        self.sizes = configs['window_size'].split(',')

    
    def init_audit(self):
        proc = subprocess.Popen([
                'lighthouse', 
                '--config-path=api/utils/custom-config.js',
                '--quiet',
                self.site.site_url, 
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
        stdout_value = proc.communicate()[0]
        return stdout_value


    def get_data(self):

        try:
            stdout_value = self.init_audit() 
            # decode bytes into string
            stdout_string = stdout_value.decode('iso-8859-1')

            # clean string of any errors
            delm = '{\n  "lighthouseVersion"'
            stdout_string = delm + stdout_string.split(delm)[1]

            # encode back to bytes
            stdout_value = stdout_string.encode('iso-8859-1')

        
            if len(stdout_string) != 0:
                if 'Runtime error encountered' in stdout_string:
                    error = {'error': 'lighthouse ran into a problem',}
                    return error

                stdout_json = json.loads(stdout_value)

                # initial audits object
                audits = {
                    "seo": [],
                    "accessibility": [],
                    "performance": [],
                    "best-practices": [],
                    "lighthouse-plugin-crux": [],
                    "pwa": []
                }

                # iterating through categories to get relevant lh_audits and store them in their respective `audits = {}` obj
                for cat in audits:
                    cat_audits = stdout_json["categories"].get(cat).get("auditRefs")
                    if cat_audits is not None:
                        for a in cat_audits:
                            if int(a["weight"]) > 0:
                                audit = stdout_json["audits"][a["id"]]
                                audits[cat].append(audit)
                # changing audits names
                audits['best_practices'] = audits.pop('best-practices')
                audits['crux'] = audits.pop('lighthouse-plugin-crux')
                
                # get scores from each category
                seo_score = round(stdout_json["categories"]["seo"]["score"] * 100)
                accessibility_score = round(stdout_json["categories"]["accessibility"]["score"] * 100)
                performance_score = round(stdout_json["categories"]["performance"]["score"] * 100)
                best_practices_score = round(stdout_json["categories"]["best-practices"]["score"] * 100)
                pwa_score = round(stdout_json["categories"]["pwa"]["score"] * 100)
                
                # attempting crux
                try:
                    crux_score = round(stdout_json["categories"]["lighthouse-plugin-crux"]["score"] * 100)
                except:
                    crux_score = 0

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

                scores = {
                    "seo": seo_score,
                    "accessibility": accessibility_score,
                    "performance": performance_score,
                    "best_practices": best_practices_score,
                    "pwa": pwa_score,
                    "crux": crux_score,
                    "average": average_score
                }


                data = {
                    "scores": scores, 
                    "audits": audits,
                    "failed": False
                }


        except Exception as e:
            print(e)

            scores = {
                "seo": None,
                "accessibility": None,
                "performance": None,
                "best_practices": None,
                "pwa": None,
                "crux": None,
                "average": None
            }

            audits = {
                "seo": [],
                "accessibility": [],
                "performance": [],
                "best_practices": [],
                "pwa": [],
                "crux": []
            }

            data = {
                "scores": scores, 
                "audits": audits,
                "failed": True
            }
            
        return data
