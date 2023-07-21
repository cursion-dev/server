import requests
from bs4 import BeautifulSoup




class Crawler():

    def __init__(self, url=None, sitemap=None, max_urls=25):
        self.url = url
        self.sitemap = sitemap
        self.max_urls = max_urls

    
    def get_links(self):

        follow_urls = []
        crawled_urls = [self.url,]
        
        def add_urls(start_url):
            reqs = requests.get(start_url)
            soup = BeautifulSoup(reqs.text, 'html.parser')
            for link in soup.find_all('a'):
                url = link.get('href')
                if url is not None:
                    if (url.startswith(self.url) or url.startswith('/')) and 'cdn-cgi' not in url:
                        if url.startswith('/'):
                            url = self.url + url
                        # check status of page
                        if requests.get(url).status_code == 200:
                            if url.endswith('/'):
                                url = url.rstrip('/')
                            if not url in follow_urls and '#' not in url:
                                follow_urls.append(url)
            
        # layer 0
        add_urls(self.url)

        # iterate through layers
        while (len(follow_urls) > len(crawled_urls)) and (len(crawled_urls) < self.max_urls):
            for url in follow_urls:
                if not url in crawled_urls:
                    crawled_urls.append(url)
                    print(url)
                    add_urls(url)
                if len(crawled_urls) >= self.max_urls:
                    print('max pages reached')
                    break

        
        return crawled_urls


