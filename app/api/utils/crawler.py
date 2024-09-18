from bs4 import BeautifulSoup
from .driver import *






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
        crawled_urls = []
        saved_urls = [self.url,]
        

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


        def crawl_url(start_url: str=None, max_depth: int=5):

            print(f'starting crawl on -> {start_url}')

            # adding url to list of crawled_urls
            crawled_urls.append(start_url)
            
            # setting depth
            depth = 0

            # get requested start_url
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
                
                # check if max_depth has been reached
                if depth >= max_depth:
                    break
                
                url = link.get('href')
                if url is not None:
                    # validate url
                    if url_is_valid(url):
                        if url.startswith('/'):
                            url = self.url + url
                        
                        # check status of page
                        self.driver.get(url)

                        print(f'looped to this url -> {url}')

                        # wait for page to load
                        resolved = driver_wait(
                            driver=self.driver,
                            max_wait_time=20, 
                            interval=2
                        )

                        # skipping url if not responding
                        if not resolved:
                            print('not resolved')
                            continue
                        
                        # clean and decide to record url
                        if str(self.driver.current_url) == str(url):
                            if url.endswith('/'):
                                url = url.rstrip('/')
                            if not (url in follow_urls):
                                follow_urls.append(url)
                                depth += 1
                                print(f'{depth} urls saved of {max_depth} allowed')
            
    
        def record_urls():
            # adds all follow_urls to saved_urls
            # if not already recorded
            
            max_reached = False
            
            # iterate through existing follow_urls
            for url in follow_urls:
                # pass if already crawled
                if not url in crawled_urls:
                    if not url in saved_urls:
                        saved_urls.append(url)
                        print(f'saving -> {url}')
                    if len(saved_urls) >= self.max_urls:
                        print('max pages reached')
                        max_reached = True
                        break
            return max_reached
       
        # layer 0
        crawl_url(self.url, max_depth=self.max_urls)

        # iterate through layers
        while (len(follow_urls) > len(saved_urls)) and (len(saved_urls) < self.max_urls):
            
            # crawl each follow_url that 
            # has not been crawled
            for url in follow_urls:
                # add existing follow_urls first
                max_reached = record_urls()
                if max_reached:
                    break
                
                # crawl new url if not in crawled_urls
                if not url in crawled_urls:
                    crawl_url(url, max_depth=self.max_urls)


        # quit driver and return
        quit_driver(self.driver)
        return saved_urls


