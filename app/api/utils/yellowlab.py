import subprocess, json
from ..models import Site, Scan



class Yellowlab():

    """Initializes Yellow Lab Tools CLI and runs an audit of the site"""


    def __init__(self, site=None, configs=None):
        self.site = site
        self.configs = configs

    
    def init_audit(self):
        proc = subprocess.Popen([
                'yellowlabtools', 
                self.site.site_url,
                f'--device={self.configs["device"]}'
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
        
            if len(stdout_string) != 0:
                if 'Runtime error encountered' in stdout_string:
                    error = {'error': 'yellowlab ran into a problem',}
                    return error

                stdout_json = json.loads(stdout_value)

                # initial audits object
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
                requests_score = stdout_json["scoreProfiles"]["generic"]["categories"]["requests"]["categoryScore"]
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
                    "requests": requests_score, 
                    "domComplexity": domComplexity_score, 
                    "javascriptComplexity": javascriptComplexity_score,
                    "badJavascript": badJavascript_score,
                    "jQuery": jQuery_score,
                    "cssComplexity": cssComplexity_score,
                    "badCSS": badCSS_score,
                    "fonts": fonts_score,
                    "serverConfig": serverConfig_score,
                }

                data = {
                    "scores": scores, 
                    "audits": audits,
                    "failed": False
                }

        except Exception as e:
            print(e)

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
        

