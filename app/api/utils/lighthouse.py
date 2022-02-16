import subprocess, json
from ..models import Site, Scan



class Lighthouse():

    """Initializes Google's Lighthouse CLI and runs an audit of the site"""


    def __init__(self, site=None):
        self.site = site

    
    def init_audit(self):
        proc = subprocess.Popen([
                'lighthouse', 
                '--config-path=api/utils/custom-config.js',
                '--quiet',
                self.site.site_url, 
                '--chrome-flags="--no-sandbox --headless"', 
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
            stdout_string = str(stdout_value)
        
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
                }

                # iterating through categories to get relevant lh_audits and store them in their respective `audits = {}` obj
                for cat in audits:
                    cat_audits = stdout_json["categories"][cat]["auditRefs"]
                    for a in cat_audits:
                        if int(a["weight"]) > 0:
                            audit = stdout_json["audits"][a["id"]]
                            audits[cat].append(audit)
                # changing audits name of best-practices to best_practices
                audits['best_practices'] = audits.pop('best-practices')
                
                # get scores from each category
                seo_score = round(stdout_json["categories"]["seo"]["score"] * 100)
                accessibility_score = round(stdout_json["categories"]["accessibility"]["score"] * 100)
                performance_score = round(stdout_json["categories"]["performance"]["score"] * 100)
                best_practices_score = round(stdout_json["categories"]["best-practices"]["score"] * 100)
                average_score = (seo_score + accessibility_score + performance_score + best_practices_score)/4

                scores = {
                    "seo": seo_score,
                    "accessibility": accessibility_score,
                    "performance": performance_score,
                    "best_practices": best_practices_score,
                    "average": average_score,
                }


                data = {
                    "scores": scores, 
                    "audits": audits
                }


        except Exception as e:
            print(e)

            scores = {
                "seo": None,
                "accessibility": None,
                "performance": None,
                "best_practices": None,
                "average": None,
            }

            audits = {
                "seo": [],
                "accessibility": [],
                "performance": [],
                "best-practices": [],
            }

            data = {
                "scores": scores, 
                "audits": audits
            }
            
        return data
