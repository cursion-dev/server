from io import StringIO
import os, fileinput, glob, subprocess, time, sys, json
from ..models import Site, Scan
from django.forms.models import model_to_dict



class Lighthouse():

    """Initialized Google's Lighthouse CLI and runs an audit of the site"""


    def __init__(self, site=None):
        self.site = site

    
    def init_audit(self):
        proc = subprocess.Popen([
                'lighthouse', 
                '--config-path=api/scan_tests/custom-config.js',
                '--quiet',
                self.site.site_url, 
                '--chrome-flags="--no-sandbox --headless"', 
                '--output',
                'json', 
                ], 
            stdout=subprocess.PIPE,
        )
        stdout_value = proc.communicate()[0]
        return stdout_value


    def scores(self):

        try:
            stdout_value = self.init_audit() 
            stdout_string = str(stdout_value)
        
            if len(stdout_string) != 0:
                if 'Runtime error encountered' in stdout_string:
                    data = {'error': 'lighthouse ran into a problem',}
                    return data

                stdout_json = json.loads(stdout_value)

                seo = round(stdout_json["categories"]["seo"]["score"] * 100)
                accessibility = round(stdout_json["categories"]["accessibility"]["score"] * 100)
                performance = round(stdout_json["categories"]["performance"]["score"] * 100)
                best_practices = round(stdout_json["categories"]["best-practices"]["score"] * 100)
                average = (seo + accessibility + performance + best_practices)/4

                scores = {
                    "seo": str(seo),
                    "accessibility": str(accessibility),
                    "performance": str(performance),
                    "best_practices": str(best_practices),
                    "average": str(average),
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
            
        return scores
