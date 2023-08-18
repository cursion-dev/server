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

        # validates url
        def url_is_valid(url):
            bad_str_list = ['cdn-cgi']
            bad_end_list = [
                '.png', '.jpg', '.pdf', '.jpeg', 
                '.json', '.doc', '.svg', '.ppt', 
                '.pptx', '.ods', '.docx', '.mp3',
                '.mp4', '.wma', '.ogg', '.mpa', 
                '.wpl', '.zip', '.pkg', '.tar.gz', 
                '.deb', '.z', '.rpm', '.7z', '.bin', 
                '.dmg', '.iso', '.toast', '.vcd',
                '.csv', 'xml', '.db', '.dbf', '.dat',
                '.log', '.mdb', '.sql', '.tar', '.sav',
                '.webp', '.tiff', '.tif', '.psd', '.ps',
                '.ico', '.gif', '.bmp'
            ]
            if not url.startswith(self.url) and not url.startswith('/'):
                return False
            for bad_str in bad_str_list:
                if bad_str in url:
                    return False
            for bad_end in bad_end_list:
                if url.endswith(bad_end):
                    return False
            return True

        
        def add_urls(start_url):
            reqs = requests.get(start_url)
            soup = BeautifulSoup(reqs.text, 'html.parser')
            for link in soup.find_all('a'):
                url = link.get('href')
                if url is not None:
                    if url_is_valid(url):
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


