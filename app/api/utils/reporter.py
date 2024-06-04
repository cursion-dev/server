from ..models import *
from scanerr import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
import os, json, boto3, textwrap, requests






class Reporter():
    """ 
    Used for generating web vitals reports for 
    the associated `Page` & `Scan`

    Expects -> {
        'report': <report:obj>,
        'scan'  : <scan:obj>,
    }

    Use self.generate_report() to create a new report

    Returns -> data: {
        'report' : object,
        'success': bool,
        'message': str
    }
    """




    def __init__(self, report: object, scan: object=None):
        
        # getting report, scan, & page
        self.report = report
        self.page = self.report.page
        self.scan = scan

        # retrieveing latest scan if none
        if scan is None:
            try:
                self.scan = Scan.objects.get(id=self.page.info['latest_scan']['id'])
            except:
                self.scan = None

        
        # building paths & canvas template
        if os.path.exists(os.path.join(settings.BASE_DIR,  f'temp/')):
            self.local_path = os.path.join(settings.BASE_DIR,  f'temp/{self.report.id}.pdf')
        else:
            os.makedirs(f'{settings.BASE_DIR}/temp')
            self.local_path = os.path.join(settings.BASE_DIR,  f'temp/{self.report.id}.pdf')
    
        # setting default colors 
        self.page_index = 0
        self.text_color = self.report.info['text_color']
        self.highlight_color = self.report.info['highlight_color']
        self.background_color = self.report.info['background_color']
        self.c = canvas.Canvas(self.local_path, letter)
        self.y = 9

        # define s3 instance
        self.s3 = boto3.client('s3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

    


    def setup_page(self) -> None:
        # sets the defaults for a new page
        self.c.setFillColor(HexColor(self.background_color))
        self.c.rect(0, 0, 8.5*inch, 11*inch, stroke=0, fill=1)
        return None




    def end_page(self) -> None:
        # adds page number and ends page
        self.c.setFont('Helvetica-Bold', 15)
        self.c.setFillColor(HexColor(self.text_color))
        self.page_index += 1
        self.c.drawString(7.7*inch, .3*inch, str(self.page_index))
        self.c.showPage()
        return None




    def draw_page_title(self, title: str) -> None:
        # adds a title to the given page 
        self.c.setFont('Helvetica-Bold', 32)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawCentredString(4.25*inch, 10*inch, title)
        return None




    def publish_report(self) -> None:
        # saves report and uploads to s3
        self.c.save()
        remote_path = f'static/sites/{self.report.page.site.id}/{self.report.page.id}/{self.report.id}.pdf'
        # uploading package to remote s3 
        with open(self.local_path, 'rb') as data:
            self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME),
                remote_path, ExtraArgs={
                    'ACL': 'public-read', 'ContentType': 'application/pdf'}
            )
        # building and saving report_url
        report_url = f'{settings.AWS_S3_URL_PATH}/{remote_path}#toolbar=0'
        self.report.path = report_url
        self.report.save()
        os.remove(self.local_path)
        return None




    def draw_wrapped_line(
            self, 
            text: str, 
            length: int, 
            x_pos: int, 
            y_pos: int, 
            y_offset: int
        ) -> None:
        """
        :param text: the raw text to wrap
        :param length: the max number of characters per line
        :param x_pos: starting x position
        :param y_pos: starting y position
        :param y_offset: the amount of space to leave between wrapped lines
        """
        # Wraps the passed test at a certain char_length
        if len(text) > length:
            wraps = textwrap.wrap(text, length, break_long_words=True)
            for x in range(len(wraps)):
                self.c.drawString(x_pos*inch, y_pos*inch, wraps[x])
                y_pos -= y_offset
            y_pos += y_offset  # add back offset after last wrapped line
        else:
            self.c.drawString(x_pos*inch, y_pos*inch, text)
        return None

    


    def cover_page(self) -> None:
        """ 
        Builds the cover page with a title

        Returns -> None
        """

        # background and title
        self.setup_page()
        
        # creating dark triangle
        p = self.c.beginPath()
        p.moveTo(0*inch, 11*inch)
        p.lineTo(7*inch, 11*inch)
        p.lineTo(2.5*inch, 4.5*inch)
        p.lineTo(0*inch, 7*inch)
        self.c.setFillColor(HexColor('#00000026', hasAlpha=True))
        self.c.setStrokeColor(HexColor('#00000026', hasAlpha=True))
        self.c.drawPath(p, fill=1)

        # crating light triangle
        p = self.c.beginPath()
        p.moveTo(0*inch, 0*inch)
        p.lineTo(0*inch, 7*inch)
        p.lineTo(7*inch, 0*inch)
        self.c.setFillColor(HexColor('#0000000D', hasAlpha=True))
        self.c.setStrokeColor(HexColor('#0000000D', hasAlpha=True))
        self.c.drawPath(p, fill=1)

        # date
        date = f'{self.scan.time_created.month}/{self.scan.time_created.day}/{self.scan.time_created.year}'
        self.c.setFont('Helvetica-Bold', 24)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(.5*inch, 7.5*inch, date)

        # title
        self.c.setFont('Helvetica-Bold', 45)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(.5*inch, 10*inch, 'Web Vitals for')
        
        # page url
        font_size = max((30 * (26/len(self.page.page_url))), 16)
        self.c.setFont('Helvetica-Bold', font_size)
        self.draw_wrapped_line(text=self.page.page_url, length=65, x_pos=.5, y_pos=9, y_offset=.5)

        # if len(self.page.page_url) <= 12:
        #     self.c.setFont('Helvetica-Bold', 30)
        #     self.c.drawString(.5*inch, 9*inch, self.page.page_url)
        
        # elif 12 < len(self.page.page_url):
        #     extra_chars = len(self.page.page_url) - 12
        #     m = (2/5)
        #     y_offset = .5
        #     length = int(20 + (extra_chars * m))
        #     self.c.setFont('Helvetica-Bold', int(45 - (extra_chars * m)))
        #     self.c.setFillColor(HexColor(self.text_color))
        #     self.draw_wrapped_line(text=self.page.page_url, length=length, x_pos=.5, y_pos=9, y_offset=y_offset)
        
        # cover img
        cover_img = os.path.join(settings.BASE_DIR, "api/utils/report_assets/cover_img.png")
        self.c.drawImage(cover_img, 1*inch, 2*inch, 6.04*inch, 4.68*inch, mask='auto')
        self.end_page()
        return None
        


    
    def get_score_data(self, score: float, is_binary: bool=False) -> dict:
        """ 
        Using the passed 'score', decide on 
        which grade and color to return.

        Expects: {
            'score'     : float,
            'is_binary' : bool
        }

        Returns -> dict
        """

        # calc score if binary
        score = float(score)
        if is_binary:
            score = score*100

        # defining score types
        score_types = {
            "a": {
                "grade": "A",
                "color": "#38B43F",
            },
            "b": {
                "grade": "B",
                "color": "#82B436",
            },
            "c": {
                "grade": "C",
                "color": "#ACB43C",
            },
            "d": {
                "grade": "D",
                "color": "#B49836",
            },
            "e": {
                "grade": "E",
                "color": "#B46B34",
            },
            "f": {
                "grade": "F",
                "color": "#B43A29",
            },

        }

        # calculate grade
        if score >= 80:
            grade = score_types['a']
        elif 80 > score >= 70:
            grade = score_types['b']
        elif 70 > score >= 50:
            grade = score_types['c']
        elif 50 > score >= 30:
            grade = score_types['d']
        elif 30 > score >= 0:
            grade = score_types['e']
        else:
            grade = score_types['f']

        # return
        return grade




    def get_cat_string(self, cat: str) -> str:
        """ 
        Returns the string coresponding to the passed 'cat'
        """
        
        if cat == 'fonts':
            string = 'Fonts'
        elif cat == 'badCSS':
            string = 'Bad CSS'
        elif cat == 'jQuery':
            string = 'jQuery'
        elif cat == 'images':
            string = 'Images'
        elif cat == 'pageWeight':
            string = 'Page Weight'
        elif cat == 'serverConfig':
            string = 'Server Config'
        elif cat == 'badJavascript':
            string = 'Bad JS'
        elif cat == 'cssComplexity':
            string = 'CSS Complexity'
        elif cat == 'domComplexity':
            string = 'DOM Complexity'
        elif cat == 'javascriptComplexity':
            string = 'JS Complexity'
        elif cat == 'seo':
            string = 'SEO'
        elif cat == 'pwa':
            string = 'PWA'
        elif cat == 'crux':
            string = 'CRUX'
        elif cat == 'best_practices' or cat == 'best-practices':
            string = 'Best Practices'
        elif cat == 'performance':
            string = 'Performance'
        elif cat == 'accessibility':
            string = 'Accessibility'

        return string

    
    

    def get_audits(self, uri: str) -> dict:
        """
        Downloads the JSON file from the passed uri
        and return the data as a python dict
        """
        res = requests.get(uri)
        audits = res.json()
        return audits




    def create_data(self, data_type: str) -> None:
        """ 
        Paints the data for the passed 'data_type', 
        either 'lighthouse' or 'yellowlab'.
        
        Expects: {
            'data_type': str
        }

        Returns -> None
        """
        
        # add new page
        self.setup_page()
        
        # decide on which data type
        if data_type == 'yellowlab':
            data = self.scan.yellowlab
            data['audits'] = self.get_audits(data['audits'])
            page_title = 'Yellow Lab'
            avg_score = 'globalScore'

        if data_type == 'lighthouse':
            data = self.scan.lighthouse
            data['audits'] = self.get_audits(data['audits'])
            page_title = 'Lighthouse'
            avg_score = 'average'
            
        self.draw_page_title(page_title)
        if data['scores'][avg_score] is None:
            return False

        # measurements
        space = .25
        text_space = .05
        begin_y = 8
        log_margin = 3.7
        text_margin = .3
        value_margin = 3
        log_height = .2
        log_width = 4
        grade_tab_width = .07

        c_count = 0
        logs_count = 0
        for cat in data['audits']:

            # checking if cat is not null
            if data['scores'][cat] is not None:

                # creating global score
                if c_count == 0:
                    grade_obj = self.get_score_data(data['scores'][avg_score])
                    self.c.setFillColor(HexColor(grade_obj['color'],))
                    self.c.roundRect(
                        2*inch, 
                        8.7*inch, 
                        1*inch, 
                        1*inch,
                        .17*inch, 
                        stroke=0, 
                        fill=1
                    )
                    self.c.setFillColor(HexColor(self.text_color))
                    self.c.setFont('Helvetica', 30)
                    self.c.drawCentredString(
                        2.5*inch, 
                        9.05*inch,
                        grade_obj['grade']
                    )
                    self.c.setFont('Helvetica', 20)
                    self.c.drawCentredString(
                        5.5*inch, 
                        8.9*inch,
                        'Global Score'
                    )
                    self.c.setFont('Helvetica-Bold', 20)
                    self.c.drawCentredString(
                        5.5*inch, 
                        9.25*inch,
                        f'{data["scores"][avg_score]}/100'
                    )

                # creating new page at limit --> 20 items
                if logs_count >= 20:
                    self.end_page()
                    logs_count = 0
                    begin_y = 9
                    self.setup_page()
                    self.draw_page_title(f'{page_title} (continued)')

                # creating space btw sections
                if c_count > 0 and logs_count != 0:
                    begin_y = (self.y - .2)

                # creating individual grade cards
                grade_obj = self.get_score_data(data['scores'][cat])
                self.c.setFillColor(HexColor(grade_obj['color'],))
                self.c.roundRect(
                    .5*inch, 
                    (begin_y - .25)*inch, 
                    .5*inch, 
                    .5*inch,
                    .12*inch, 
                    stroke=0, 
                    fill=1
                )
                self.c.setFillColor(HexColor(self.text_color))
                self.c.setFont('Helvetica', 16)
                self.c.drawCentredString(
                    .75*inch, 
                    (begin_y - .07)*inch,
                    grade_obj['grade']
                )

                self.c.setFont('Helvetica', 16)
                cat_string = self.get_cat_string(cat)
                self.c.drawCentredString(
                    2.3*inch, 
                    (begin_y - .07)*inch,
                    cat_string
                )

                p_count = 0
                for policy in data['audits'][cat]:

                    if (begin_y - (space * p_count)) < 1:
                        break

                    # setting up keys for dict(s)
                    if data_type == 'yellowlab':
                        policy_text = policy["policy"]["label"]
                        policy_value = policy["value"]
                        binary = False
                    if data_type == 'lighthouse':
                        policy_text = policy["title"]
                        policy_value = ''
                        if "displayValue" in policy:
                            if len(policy["displayValue"]) < 9:
                                policy_value = policy["displayValue"]
                        binary = True

                    if len(policy_text) < 53:
                        # creating log box
                        self.c.setFont('Helvetica', 9)
                        self.c.setFillColor(HexColor(f'{self.highlight_color}95', hasAlpha=True))
                        self.c.rect(
                            log_margin*inch, 
                            (begin_y - (space * p_count))*inch, 
                            log_width*inch, log_height*inch, 
                            stroke=0, 
                            fill=1
                        )
                        
                        # get grade tab
                        grade_obj = self.get_score_data(policy['score'], is_binary=binary)
                        self.c.setFillColor(HexColor(grade_obj['color'],)) 
                        self.c.rect(
                            log_margin*inch, 
                            (begin_y - (space * p_count))*inch, 
                            grade_tab_width*inch, 
                            log_height*inch, 
                            stroke=0, 
                            fill=1
                        )
                        
                        # inserting data
                        self.c.setFillColor(HexColor(self.text_color))

                        # text
                        self.c.drawString(
                            (log_margin + text_margin)*inch,
                            ((begin_y - (space * p_count)) + text_space)*inch, 
                            (f'{policy_text}')
                        )
                        
                        # value
                        self.c.drawString(
                            (value_margin + text_margin + log_margin)*inch, 
                            ((begin_y - (space * p_count)) + text_space)*inch, 
                            (f'{policy_value}')
                        )
                        
                        p_count += 1
                        logs_count += 1
                        self.y = (begin_y - (space * p_count))
            
            c_count += 1
        
        self.end_page()

        return None





    def generate_report(self) -> dict:
        """ 
        Generates a new Report.

        Returns -> data: {
            'report' : object,
            'success': bool,
            'message': str
        }
        """

        # setting defaults
        message = 'Scan Page first'
        success = False

        # generating if scan is available
        if self.scan:
            
            # add title
            self.cover_page()
        
            # build lighthouse data
            if 'lighthouse' in self.report.type or 'full' in self.report.type:
                self.create_data(data_type='lighthouse')

            # build yellowlab data
            if 'yellowlab' in self.report.type or 'full' in self.report.type:
                self.create_data(data_type='yellowlab')
            
            # save report
            self.publish_report()
            message = 'Report Generated'
            success = True
        
        # formating response
        data = {
            'report' : self.report,
            'success': success,
            'message': message
        }

        # returning response
        return data


        



    