import requests, os, json



class Crux():

    def __init__(self, site_url):
        self.site_url = site_url
        self.key = os.environ.get('GOOGLE_CRUX_KEY')


    def get_data(self):

        url = f'https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={self.key}'
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "origin": str(self.site_url),
        }

        res = requests.post(
            url=url, 
            headers=headers, 
            data=json.dumps(data)
        )

        response = res.json()

        if res.status_code != 200:
            response = {
                "status": "failed",
                "message": "This site_url does not have enough historical data in the CRUX API to respond with."
            }
        
        return response
