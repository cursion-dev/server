# from pyppeteer import launch
# from cursion import settings
# import time, os, sys, datetime






# async def driver_init(window_size: str='1920,1080', wait_time: int=30) -> object:
#     """ 
#     Starts a new puppeteer driver instance

#     Args:
#         'window_size' : str, 
#         'wait_time'   : int
#     } 

#     Returns: driver object
#     """

#     # parsing window sizes
#     sizes = window_size.split(',')

#     # setting browser options
#     options = {
#         'executablePath': os.environ.get('CHROME_BROWSER'),
#         'args': [
#             '--no-sandbox', 
#             '--disable-dev-shm-usage',
#             '--force-device-scale-factor=0.5',
#             'ignore-certificate-errors',
#             '--hide-scrollbars',
#             f'--window-size={window_size}',
#         ],
#         'defaultViewport': {
#             'width': int(sizes[0]),
#             'height': int(sizes[1]), 
#         },
#         # 'timeout': wait_time * 1000
#     }

#     # launching driver
#     driver = await launch(
#         options=options, 
#         headless=True,
#         handleSIGINT=False,
#         handleSIGTERM=False,
#         handleSIGHUP=False
#     )
    
#     # return driver
#     return driver




# async def interact_with_page(page: object=None) -> object:
#     # simulate mouse movement
#     # and returns the page object
#     await page.mouse.move(0, 0)
#     await page.mouse.move(0, 50)
#     return page




# async def wait_for_page(page: object=None, max_wait_time: int=30) -> object:
#     """
#     Expects the puppeteer page instance and waits 
#     for either the page to fully load or the max_wait_time
#     to expire before returning.

#     Args:
#         'page'          : object, 
#         'max_wait_time' : int
#     }

#     Returns: page <pypt:instance>
#     """

#     print(f'waiting for page load or {str(max_wait_time)} seconds')

#     timeout = 0
#     page_state = 'loading'

#     while int(timeout) < int(max_wait_time) and page_state != 'complete':
#         page_state = await page.evaluate('document.readyState')
#         print(f'document state is {page_state}')
#         time.sleep(1)
#         timeout += 1

#     return page




# async def driver_test() -> None:
#     """ 
#     Spins up a puppeteer driver instance and
#     tests to ensure it can access the browser and internet

#     Returns: None
#     """

#     print("Testing puppeteer instalation and integration...")
#     message = 'Puppeteer was unable to start\n\n'
#     status = 'Failed'

#     # testing puppeteer
#     try:
#         driver = await driver_init()
#         page = await driver.newPage()
#         await page.goto('https://google.com', {'waitUntil': 'networkidle0'})
#         await interact_with_page(page)
#         title = await page.title()
#         assert title == 'Google'
#         if title == 'Google':
#             status = 'Success'
#             message = 'Puppeteer installed and working \N{check mark} \n'

#     # log exception
#     except Exception as e:
#         print(e)

#     # logging test results
#     sys.stdout.write(
#         '--- ' + status + ' ---\n'+ message
#     )

#     # quiting driver
#     try:
#         await driver.close()
#     except:
#         pass
    
#     return None
   



# async def get_data(url: str=None, configs: dict=None) -> dict:
#     """ 
#     Using the puppeteer driver, navigates to the passed 
#     'url' and records the page source and any 
#     present console errors & warnings

#     Args:
#         url     : str, 
#         configs : dict
#     }
    
#     Returns:
#         'html' : str, 
#         'logs' : dict,
#     }
#     """

#     # initing the driver
#     sizes = configs['window_size'].split(',')
#     driver = await driver_init(window_size=configs['window_size'])
#     page = await driver.newPage()

#     # setting driver configs
#     page_options = {
#         'waitUntil': 'networkidle0', 
#         # 'timeout': configs['max_wait_time']*1000
#     }
#     viewport = {
#         'width': int(sizes[0]),
#         'height': int(sizes[1]),
#     }
#     userAgent = (
#         "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
#         (KHTML, like Gecko) Chrome/122.0.6261.119 Safari/537.36"
#     )
#     await page.setViewport(viewport)
#     if configs['device'] == 'mobile':
#         await page.setUserAgent(userAgent)
    
#     # defining logs
#     logs = []

#     def record_logs(log):
#         # helper method to record console
#         # logs in the issues tab
#         if log.type == 'error':
#             if '.js' in log.text:
#                 source = 'javascript'
#             elif 'http' in log.text:
#                 source = 'network'
#             else:
#                 source = 'other'
#             log_obj = {
#                 "level": "SEVERE", 
#                 "source": source, 
#                 "message": str(log.text),
#                 "timestamp": int(datetime.datetime.now().timestamp() * 1000)
#             }
#             logs.append(log_obj)
#         elif log.type == 'warning':
#             if '.js' in log.text:
#                 source = 'javascript'
#             elif 'http' in log.text:
#                 source = 'network'
#             else:
#                 source = 'other'
#             log_obj = {
#                 "level": "WARNING",
#                 "source": source,
#                 "message": str(log.text),
#                 "timestamp": int(datetime.datetime.now().timestamp() * 1000)
#             }
#             logs.append(log_obj)
    
#     def record_network(request):
#         # helper method to record console
#         # network issues in the issues tab
#         log_obj = {
#             "level": "SEVERE", 
#             "source": "network",
#             "message": f'{request.failure()["errorText"]} {request.url}',
#             "timestamp": int(datetime.datetime.now().timestamp() * 1000)
#         }
#         logs.append(log_obj)

#     def record_error(error):
#         # helper method to record console
#         # page errors in the issues tab
#         err = str(error).split(' at ')[0]
#         log_obj = {
#             "level": "SEVERE", 
#             "source": "javascript",
#             "message": f'{err}',
#             "timestamp": int(datetime.datetime.now().timestamp() * 1000)
#         }
#         logs.append(log_obj)

#     # getting console logs, warnings, and errors
#     page.on('console', lambda log : record_logs(log))
#     page.on('requestfailed', lambda request : record_network(request))
#     page.on('pageerror', lambda error : record_error(error))

#     # navigate to requested url
#     await page.goto(url, page_options) 

#     # await page.waitForNavigation(navWaitOpt)
#     await wait_for_page(page=page)
#     await interact_with_page(page)
#     html = await page.content()
    
#     # quitting driver
#     await driver.close()
    
#     # returning data
#     data = {
#         'html': html, 
#         'logs': logs,
#     }

#     return data


