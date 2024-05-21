from pyppeteer import launch
from scanerr import settings
import time, os, numpy, json, \
sys, datetime, asyncio, subprocess



async def driver_init(
    window_size='1920,1080',
    wait_time=30, 
    ):

    sizes = window_size.split(',')

    options = {
        'executablePath': os.environ.get('CHROME_BROWSER'),
        'args': [
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--force-device-scale-factor=0.5',
            'ignore-certificate-errors',
            '--hide-scrollbars',
            f'--window-size={window_size}',
        ],
        'defaultViewport': {
            'width': int(sizes[0]),
            'height': int(sizes[1]), 
        },
        # 'timeout': wait_time * 1000  # replaced by 
    }

    driver = await launch(
        options=options, 
        headless=True,
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    
    return driver





async def interact_with_page(page):
    # simulate mouse movement
    await page.mouse.move(0, 0)
    await page.mouse.move(0, 50)

    return page



async def wait_for_page(page, max_wait_time=30):
    """
    Expects the puppeteer page instance and waits 
    for either the page to fully load or the max_wait_time
    to expire before returning.

    Returns -> Page <pypt:instance>
    """

    print(f'waiting for page load or {str(max_wait_time)} seconds')

    timeout = 0
    page_state = 'loading'

    while int(timeout) < int(max_wait_time) and page_state != 'complete':
        page_state = await page.evaluate('document.readyState')
        print(f'document state is {page_state}')
        time.sleep(1)
        timeout += 1

    return page



async def driver_test(*args, **options):

    print("Testing puppeteer instalation and integration...")
    message = 'Puppeteer was unable to start\n\n'
    status = 'Failed'

    try:
        driver = await driver_init()
        page = await driver.newPage()
        await page.goto('https://google.com', {'waitUntil': 'networkidle0'})
        await interact_with_page(page)
        title = await page.title()
        assert title == 'Google'
        if title == 'Google':
            status = 'Success'
            message = 'Puppeteer installed and working \N{check mark} \n'

    except Exception as e:
        print(e)

    sys.stdout.write(
            '--- ' + status + ' ---\n'+ message
        )

    try:
        await driver.close()
    except:
        pass
   





async def get_data(url, configs, *args, **options):
    sizes = configs['window_size'].split(',')
    driver = await driver_init(window_size=configs['window_size'])
    page = await driver.newPage()

    page_options = {
        'waitUntil': 'networkidle0', 
        # 'timeout': configs['max_wait_time']*1000
    }

    viewport = {
        'width': int(sizes[0]),
        'height': int(sizes[1]),
    }
    
    userAgent = (
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/122.0.6261.119 Safari/537.36"
    )

    await page.setViewport(viewport)

    if configs['device'] == 'mobile':
        await page.setUserAgent(userAgent)
    
    
    logs = []
    def record_logs(log):
        if log.type == 'error':
            if '.js' in log.text:
                source = 'javascript'
            elif 'http' in log.text:
                source = 'network'
            else:
                source = 'other'
            log_obj = {
                "level": "SEVERE", 
                "source": source, 
                "message": str(log.text),
                "timestamp": int(datetime.datetime.now().timestamp() * 1000)
            }
            logs.append(log_obj)
        elif log.type == 'warning':
            if '.js' in log.text:
                source = 'javascript'
            elif 'http' in log.text:
                source = 'network'
            else:
                source = 'other'
            log_obj = {
                "level": "WARNING",
                "source": source,
                "message": str(log.text),
                "timestamp": int(datetime.datetime.now().timestamp() * 1000)
            }
            logs.append(log_obj)
    
    def record_network(request):
        log_obj = {
            "level": "SEVERE", 
            "source": "network",
            "message": f'{request.failure()["errorText"]} {request.url}',
            "timestamp": int(datetime.datetime.now().timestamp() * 1000)
        }
        logs.append(log_obj)

    def record_error(error):
        err = str(error).split(' at ')[0]
        log_obj = {
            "level": "SEVERE", 
            "source": "javascript",
            "message": f'{err}',
            "timestamp": int(datetime.datetime.now().timestamp() * 1000)
        }
        logs.append(log_obj)


    page.on('console', lambda log : record_logs(log))
    page.on('requestfailed', lambda request : record_network(request))
    page.on('pageerror', lambda error : record_error(error))

    await page.goto(url, page_options) 

    # await page.waitForNavigation(navWaitOpt)
    await wait_for_page(page=page)
    await interact_with_page(page)
    html = await page.content()
    
    await driver.close()

    data = {
        'html': html, 
        'logs': logs,
    }

    return data




def test_puppeteer():
    # initiating subprocess for Puppeteer
    js_file = os.path.join(settings.BASE_DIR, "api/utils/puppeteer.mjs")
    proc = subprocess.Popen(
        [
            'node',
            js_file,
        ], 
        stdout=subprocess.PIPE,
        user='app',
    )

    # retrieving data from process
    stdout_value = proc.communicate()[0]

    # converting stdout str into Dict
    stdout_json = json.loads(stdout_value)
    return stdout_json