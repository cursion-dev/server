from pyppeteer import launch
import time, os, numpy, json, sys, datetime, asyncio



async def driver_init(
    window_size='1920,1080',
    wait_time=30, 
    ):

    sizes = window_size.split(',')

    options = {
        'executablePath': os.environ.get('CHROMIUM'),
        'args': [
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--force-device-scale-factor=0.5',
            'ignore-certificate-errors'
            f'--window-size={window_size}',
        ],
        'defaultViewport': {
            'width': int(sizes[0]),
            'height': int(sizes[1]), 
        },
        'timeout': wait_time * 1000
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
    await page.mouse.move(0, 100)

    return page






async def driver_test(*args, **options):

    print("Testing puppeteer instalation and integration...")

    try:
        driver = await driver_init()
        page = await driver.newPage()
        await page.goto('https://google.com', {'waitUntil': 'networkidle0'})
        await interact_with_page(page)
        title = await page.title()
        assert title == 'Google'
        if title == 'Google':
            status = 'Success'
        else:
            status = 'Failed'
        await driver.close()
    except Exception as e:
        print(e)
        status = 'Failed'

    sys.stdout.write('--- ' + status + ' ---\n'
        + 'Puppeteer installed and working \N{check mark} \n'
        )
   





async def get_data(url, configs, *args, **options):
    sizes = configs['window_size'].split(',')
    driver = await driver_init(window_size=configs['window_size'])
    page = await driver.newPage()

    page_options = {
        'waitUntil': 'networkidle0', 
        'timeout': configs['max_wait_time']*1000
    }
    viewport = {
        'width': int(sizes[0]),
        'height': int(sizes[1]),
    }
    
    userAgent = (
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/99.0.4812.0 Safari/537.36"
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
    await interact_with_page(page)
    html = await page.content()
    
    await driver.close()

    data = {
        'html': html, 
        'logs': logs,
    }

    return data