import requests
from bs4 import BeautifulSoup
from .driver_s import *






class Crawler():
    """ 
    Crawl the passed "site" for pages, stoping 
    once 'max_urls' is reached.

    Expects: {
        'url'       : str,
        'sitemap'   : str,
        'start_url' : str,
        'max_urls'  : int,
    }

    Use `Crawler.get_links()` initiate a new crawl

    Returns -> list
    """



    def __init__(self, url: str=None, sitemap: str=None, max_urls: int=25):
        self.url = url
        self.sitemap = sitemap
        self.max_urls = max_urls
        self.driver = driver_init()



    
    def get_links(self) -> list:
        # crawl self.url and record any found links 
        # which are within the same self.url domain

        follow_urls = []
        crawled_urls = [self.url,]
        
        def url_is_valid(url: str=None) -> bool:
            # checks if the passed url is 
            # a valid url to follow and 
            # not a file or external redirect

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
            self.driver.get(start_url)

            # wait for page to load
            driver_wait(
                driver=self.driver,
                max_wait_time=20, 
                interval=2
            )

            # parsing page_source 
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # iterating through all <a> tags
            for link in soup.find_all('a'):
                url = link.get('href')
                if url is not None:
                    # validate url
                    if url_is_valid(url):
                        if url.startswith('/'):
                            url = self.url + url
                        # check status of page
                        req_status = requests.get(url).status_code
                        bad_status = [404, 500, 301]
                        if not (req_status in bad_status):
                            if url.endswith('/'):
                                url = url.rstrip('/')
                            if not (url in follow_urls):
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

        # quit driver and return
        quit_driver(self.driver)
        return crawled_urls


