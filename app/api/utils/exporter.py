from .driver import driver_init, driver_wait, quit_driver
from PIL import Image as I
from .alerts import sendgrid_email
from cursion import settings
import time, boto3, os





def create_and_send_report_export(report_id: id, email: str, first_name: str) -> dict:
    """
    Takes a screenshot of the `landing.report`, 
    save as a PDF, upload to s3 bucket, and then 
    send an email to the prospect that requested it.

    Expects the following:
        'report_id'     : id of report/page being reported on
        'email'         : str prospect's email address 
        'first_name'    : str prospect's first name
    
    Returns -> data {
        'success' : bool if process started successfully
        'error'   : str any error msg from cursion server
    }
    """

    # setting up s3 client
    s3 = boto3.client(
        's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
        region_name=str(settings.AWS_S3_REGION_NAME), 
        endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
    )

    # init driver
    driver = driver_init(scale_factor=1)

    # nav to report page
    driver.get(f'{settings.LANDING_URL_ROOT}/report/{report_id}')
    time.sleep(5)

    # wait for page to load
    driver_wait(driver=driver)

    # setting screensize
    full_page_height = driver.execute_script("return document.scrollingElement.scrollHeight;")
    driver.set_window_size(1260, int(full_page_height)) # 1512 x full_page

    # taking screenshot
    driver.save_screenshot(f'{report_id}.png')

    # quitting driver
    quit_driver(driver)

    # setting up paths
    image = os.path.join(settings.BASE_DIR, f'{report_id}.png')
    pdf = os.path.join(settings.BASE_DIR, f'{report_id}.pdf')

    # resizing image to remove excess | expected height => 2353
    img = I.open(image)
    width, height = img.size

    # Validate crop bounds
    left = 0
    top = 85
    right = width
    bottom = max(0, height - 330)

    cropped_img = img.crop((left, top, right, bottom))
    cropped_img.save(image, quality=95)

    # Convert to PDF
    img = I.open(image)
    pdf_img = img.convert('RGB')
    pdf_img.save(pdf)

    # uploading to s3
    remote_path = f'static/landing/reports/{report_id}.pdf' # -> .png
    report_url = f'{settings.AWS_S3_URL_PATH}/{remote_path}'

    # upload to s3
    with open(pdf, 'rb') as data: # -> image
        s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
            remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': 'application/pdf'}
        )

    # removing local copies
    os.remove(image)
    os.remove(pdf)
    
    # setting up email to prospect
    pre_content = 'The Cursion performance report you requested has finished processing. \
         Now, just click the link below to view and download the PDF.'
    content = 'If you have any questions about the report or want deeper insights, feel free to book a short call with me here -> https://cursion.dev/booking'
    subject = f'{first_name}, your Cursion Report is Ready'
    title = f'{first_name}, your Cursion Report is Ready'
    pre_header = f'{first_name}, your Cursion Report is Ready'
    button_text = 'View Your Report'
    email = email
    object_url = report_url
    signature = f'- Landon R | CEO <a href="https://cursion.dev">@Cursion</a>'
    greeting = f'Hi {first_name},'

    message_obj = {
        'pre_content': pre_content,
        'content': content, 
        'subject': subject, 
        'title': title, 
        'pre_header': pre_header,
        'button_text': button_text, 
        'email': email, 
        'object_url': object_url,
        'signature': signature,
        'greeting': greeting
    }

    # sending email to prospect
    data = sendgrid_email(message_obj=message_obj)

    # returning data
    return data



    

