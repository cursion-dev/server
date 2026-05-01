from ..models import *
from cursion import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from django.utils import timezone
from datetime import timedelta
import os, boto3, textwrap, requests






class Report():
    """ 
    Used for generating web vitals reports for 
    the associated `Site` & `Scan`

    Args:
        'report': <report:obj>,
        'scan'  : <scan:obj>

    Use self.generate_report() to create a new report

    Returns:
        'report' : object,
        'success': bool,
        'message': str
    """




    def __init__(self, report: object, scan: object=None):
        
        # getting report and collecting data
        self.report = report
        self.site   = self.report.site
        self.scan   = scan
        
        # ignore categories
        self.ignore_cats = ['crux', 'CRUX']

        # retrieveing latest scan if none
        if scan is None:
            try:
                self.scan = Scan.objects.filter(
                    site=self.site
                ).exclude(
                    time_completed=None
                ).order_by('-time_created')[0]
            except Exception as e:
                print(e)
                self.scan = None

        # building paths & canvas template
        if os.path.exists(os.path.join(settings.BASE_DIR, f'reports/')):
            self.local_path = os.path.join(settings.BASE_DIR, f'reports/{self.report.id}.pdf')
        else:
            os.makedirs(f'{settings.BASE_DIR}/reports')
            self.local_path = os.path.join(settings.BASE_DIR, f'reports/{self.report.id}.pdf')
    
        # setting default colors 
        self.page_index         = 0
        self.text_color         = self.report.info.get('text_color')
        self.highlight_color    = self.report.info.get('highlight_color')
        self.background_color   = self.report.info.get('background_color')
        self.card_color         = self.report.info.get('card_color','#ffffff')
        
        self.c = canvas.Canvas(self.local_path, letter)
        self.y = 9
        self.y_marg = .04

        # define s3 instance
        self.s3 = boto3.client('s3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # report-window settings
        self.lookback_days = self.get_lookback_days()
        self.window_start = timezone.now() - timedelta(days=self.lookback_days)

    


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
        remote_path = f'static/sites/{self.report.site.id}/{self.report.id}.pdf'
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
        Args:
            text: the raw text to wrap
            length: the max number of characters per line
            x_pos: starting x position
            y_pos: starting y position
            y_offset: the amount of space to leave between wrapped lines
        
        Returns:
            None
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

        Returns:
            None
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

        # date range
        start_date = self.window_start.date()
        end_date = timezone.now().date()
        date_range = f'{start_date.month}/{start_date.day}/{start_date.year} - {end_date.month}/{end_date.day}/{end_date.year}'
        self.c.setFont('Helvetica-Bold', 18)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(.5*inch, 7.5*inch, date_range)

        # title
        self.c.setFont('Helvetica-Bold', 45)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(.5*inch, 10*inch, 'Site Report for')
        
        # site url
        font_size = max((30 * (26/len(self.site.site_url))), 16)
        self.c.setFont('Helvetica-Bold', font_size)
        self.draw_wrapped_line(text=self.site.site_url, length=65, x_pos=.5, y_pos=9, y_offset=.5)
        
        # cover img
        cover_img = os.path.join(settings.BASE_DIR, "api/utils/report_assets/cover_img.png")
        self.c.drawImage(cover_img, 1*inch, 2*inch, 6.04*inch, 4.68*inch, mask='auto')
        self.end_page()
        return None
        


    
    def get_score_data(self, score: float | None, is_binary: bool=False) -> dict:
        """ 
        Using the passed 'score', decide on 
        which grade and color to return.

        Args:
            'score'     : float | NoneType,
            'is_binary' : bool

        Returns:
            dict
        """

        # check score type
        if type(score) == float:

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
            "i": {
                "grade": "I",
                "color": "#6b7280",
            }
        }

        # calculate grade
        if score == None:
            grade = score_types['i']
        elif score >= 80:
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
        
        if cat == 'seo':
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
        elif cat == 'transport':
            string = 'Transport Security'
        elif cat == 'browser':
            string = 'Browser Protections'
        elif cat == 'scripts':
            string = 'Script Safety'
        elif cat == 'forms':
            string = 'Form Security'
        elif cat == 'compliance':
            string = 'Compliance & Privacy'

        return string

    
    

    def get_audits(self, uri: str=None) -> dict:
        """
        Downloads the JSON file from the passed uri
        and return the data as a python dict
        """
        if uri:
            res = requests.get(uri)
            audits = res.json()
            return audits
        else:
            return []        
    



    def normalize_score(self, score: any=None) -> dict:
        """
        Converts the passed score into an int 
        between 0-100 or an empty string
        """
        if score == 'null' or score == None or score == '':
            return None
        if score > 1 or score == 0:
            return score
        if score <= 1:
            return score*100



    def get_lookback_days(self) -> int:
        """Returns a validated lookback value from report info."""
        lookback_days = 30
        info = self.report.info if isinstance(self.report.info, dict) else {}
        try:
            lookback_days = int(info.get('lookback_days', 30))
        except Exception:
            lookback_days = 30

        if lookback_days not in [1, 7, 30, 90]:
            lookback_days = 30
        return lookback_days



    def get_report_types(self) -> list:
        """Gets selected report types from report.type/info.types."""
        _types = self.report.type if isinstance(self.report.type, list) else []
        info_types = []
        if isinstance(self.report.info, dict):
            info_types = self.report.info.get('types', [])
        if len(_types) == 0 and isinstance(info_types, list):
            _types = info_types
        return [str(item).lower() for item in _types]



    def format_dt(self, value: any=None) -> str:
        if value is None:
            return '-'
        try:
            local_time = timezone.localtime(value)
            return local_time.strftime('%m/%d/%Y %I:%M %p')
        except Exception:
            return str(value)



    def get_lookback_scans(self) -> object:
        return Scan.objects.filter(
            site=self.site
        ).exclude(
            time_completed=None
        ).filter(
            time_completed__gte=self.window_start
        ).order_by('-time_completed')



    def get_lookback_issues(self) -> object:
        page_ids = [str(page.id) for page in Page.objects.filter(site=self.site)]
        scoped_ids = [str(self.site.id)] + page_ids

        return Issue.objects.filter(
            account=self.report.account,
            affected__id__in=scoped_ids,
            time_created__gte=self.window_start
        ).order_by('-time_created').distinct()



    def get_lookback_tests(self) -> object:
        return Test.objects.filter(
            site=self.site
        ).exclude(
            time_completed=None
        ).filter(
            time_completed__gte=self.window_start
        ).order_by('-time_completed')



    def get_lookback_caseruns(self) -> object:
        return CaseRun.objects.filter(
            site=self.site,
            account=self.report.account
        ).exclude(
            time_completed=None
        ).filter(
            time_completed__gte=self.window_start
        ).order_by('-time_completed')



    def get_audit_window_summary(self, data_type: str) -> dict:
        scans = self.get_lookback_scans()
        total = len(scans)
        averages = []
        with_score = 0
        pages = {}

        for scan in scans:
            data = scan.security if data_type == 'security' else scan.lighthouse
            score = ((data or {}).get('scores') or {}).get('average')
            if score is not None:
                with_score += 1
                score = float(score)
                averages.append(score)
                if scan.page:
                    page_id = str(scan.page.id)
                    if page_id not in pages:
                        pages[page_id] = {
                            'page_url': scan.page.page_url or str(scan.page.id),
                            'lowest_score': score,
                        }
                    else:
                        pages[page_id]['lowest_score'] = min(pages[page_id]['lowest_score'], score)

        average_score = round((sum(averages) / len(averages)), 2) if len(averages) > 0 else None
        lowest_score = round(min(averages), 2) if len(averages) > 0 else None
        top_pages = sorted(list(pages.values()), key=lambda item: item['lowest_score'])[:5]
        return {
            'total_scans': total,
            'with_score': with_score,
            'average': average_score,
            'lowest_score': lowest_score,
            'top_pages': top_pages,
        }



    def draw_audit_window_summary(self, data_type: str) -> None:
        summary = self.get_audit_window_summary(data_type)
        avg_score = round(summary['average']) if summary['average'] is not None else None
        grade_obj = self.get_score_data(avg_score) if avg_score is not None else {'color': '#3b82f6'}

        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawCentredString(4.25*inch, 8.9*inch, f'Lookback Summary ({self.lookback_days} days)')

        # average score card
        self.c.setFillColor(HexColor(f"{grade_obj['color']}3d", hasAlpha=True))
        self.c.roundRect(.6*inch, 7.2*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(grade_obj['color']))
        self.c.rect(.6*inch, 7.2*inch, .1*inch, .95*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(1.7*inch, 7.77*inch, 'Avg Score')
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(1.7*inch, 7.4*inch, f'{avg_score}' if avg_score is not None else '-')

        # scans completed card
        self.c.setFillColor(HexColor(f'{self.card_color}95', hasAlpha=True))
        self.c.roundRect(3.15*inch, 7.2*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(4.25*inch, 7.77*inch, 'Scans')
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(4.25*inch, 7.4*inch, str(summary['total_scans']))

        # lowest score card
        low_color = self.get_score_data(summary['lowest_score'])['color'] if summary['lowest_score'] is not None else '#3b82f6'
        self.c.setFillColor(HexColor(f'{low_color}3d', hasAlpha=True))
        self.c.roundRect(5.7*inch, 7.2*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(low_color))
        self.c.rect(5.7*inch, 7.2*inch, .1*inch, .95*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(6.8*inch, 7.77*inch, 'Lowest')
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(6.8*inch, 7.4*inch, f'{summary["lowest_score"]}' if summary['lowest_score'] is not None else '-')

        self.c.setFont('Helvetica', 10)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawCentredString(4.25*inch, 6.85*inch, 'Scores are calculated from completed scans in the selected window.')

        self.c.setFont('Helvetica-Bold', 13)
        self.c.drawString(.65*inch, 6.35*inch, 'Top Pages with Lowest Scores')
        y = 6.0
        if len(summary['top_pages']) == 0:
            self.c.setFont('Helvetica', 10)
            self.c.drawString(.8*inch, 5.75*inch, 'No page-level scores were found in this lookback window.')
            return None

        for idx, item in enumerate(summary['top_pages']):
            if y < 1.2:
                break
            row_score = item['lowest_score']
            row_grade = self.get_score_data(row_score)
            self.c.setFillColor(HexColor(f'{self.card_color}95', hasAlpha=True))
            self.c.rect(.65*inch, (y-.1)*inch, 7.2*inch, .22*inch, stroke=0, fill=1)
            self.c.setFillColor(HexColor(row_grade['color']))
            self.c.rect(.65*inch, (y-.1)*inch, .08*inch, .22*inch, stroke=0, fill=1)
            self.c.setFillColor(HexColor(self.text_color))
            self.c.setFont('Helvetica', 9)
            self.c.drawString(.8*inch, (y-self.y_marg)*inch, f'{idx+1}.')
            self.c.drawString(1.1*inch, (y-self.y_marg)*inch, str(item['page_url'])[:70])
            self.c.drawRightString(7.7*inch, (y-self.y_marg)*inch, f'{row_score}')
            y -= .28
        return None



    def create_audit_summary_page(self, data_type: str) -> None:
        page_title = 'Security' if data_type == 'security' else 'Lighthouse'
        self.setup_page()
        self.draw_page_title(f'{page_title} Summary')
        self.draw_audit_window_summary(data_type=data_type)
        self.end_page()
        return None



    def get_collection_rows(self, data_type: str) -> list:
        rows = []

        if data_type == 'issues':
            issues = self.get_lookback_issues()
            for issue in issues:
                affected = issue.affected if isinstance(issue.affected, dict) else {}
                bucket = self.normalize_collection_status(issue.status, data_type='issues')
                rows.append({
                    'time': issue.time_created,
                    'status': str(issue.status or 'open'),
                    'bucket': bucket,
                    'title': str(issue.title or 'Untitled Issue'),
                    'detail': f'{bucket.upper()} | {affected.get("type", "-")} : {affected.get("id", "-")}',
                })

        if data_type == 'tests':
            tests = self.get_lookback_tests()
            for test in tests:
                score = f'{round(test.score, 2)}' if test.score is not None else '-'
                page_url = test.page.page_url if test.page else 'Unknown Page'
                bucket = self.normalize_collection_status(test.status, data_type='tests')
                rows.append({
                    'time': test.time_completed,
                    'status': str(test.status or 'unknown'),
                    'bucket': bucket,
                    'title': str(page_url),
                    'detail': f'{bucket.upper()} | Score: {score}',
                })

        if data_type == 'caseruns':
            caseruns = self.get_lookback_caseruns()
            for caserun in caseruns:
                case_id = str(caserun.case.id) if caserun.case else '-'
                bucket = self.normalize_collection_status(caserun.status, data_type='caseruns')
                rows.append({
                    'time': caserun.time_completed,
                    'status': str(caserun.status or 'unknown'),
                    'bucket': bucket,
                    'title': str(caserun.title or 'Untitled CaseRun'),
                    'detail': f'{bucket.upper()} | Case: {case_id}',
                })

        return rows



    def get_status_counts(self, rows: list=None) -> dict:
        counts = {}
        if rows is None:
            return counts
        for row in rows:
            status = str(row.get('bucket', row.get('status', 'unknown'))).lower()
            counts[status] = counts.get(status, 0) + 1
        return counts



    def normalize_collection_status(self, status: str='unknown', data_type: str='issues') -> str:
        status = str(status or '').lower()
        if data_type == 'issues':
            if status in ['closed', 'resolved', 'complete', 'completed']:
                return 'closed'
            return 'open'

        if status in ['pass', 'passed', 'complete', 'completed', 'success']:
            return 'passed'
        if status in ['fail', 'failed', 'error', 'incomplete', 'blocked', 'critical']:
            return 'failed'
        if status in ['working', 'running', 'queued', 'in_progress', 'pending']:
            return 'failed'
        return 'failed'



    def get_status_color(self, status: str='unknown') -> str:
        status = str(status or '').lower()
        if status in ['closed', 'passed']:
            return '#38B43F'
        if status in ['open']:
            return '#3b82f6'
        if status in ['failed']:
            return '#B43A29'
        return '#3b82f6'



    def draw_collection_summary(self, rows: list=None, data_type: str='issues', y: float=8.7) -> float:
        status_counts = self.get_status_counts(rows=rows)
        total = len(rows or [])
        if data_type == 'issues':
            left_label = 'Closed'
            right_label = 'Open'
            left_value = status_counts.get('closed', 0)
            right_value = status_counts.get('open', 0)
        else:
            left_label = 'Passed'
            right_label = 'Failed'
            left_value = status_counts.get('passed', 0)
            right_value = status_counts.get('failed', 0)

        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawCentredString(4.25*inch, 8.95*inch, f'Lookback Summary ({self.lookback_days} days)')

        left_color = self.get_status_color(left_label)
        right_color = self.get_status_color(right_label)

        # lookback card
        self.c.setFillColor(HexColor(f'{left_color}3d', hasAlpha=True))
        self.c.roundRect(.6*inch, (y-.1)*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(left_color))
        self.c.rect(.6*inch, (y-.1)*inch, .1*inch, .95*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(1.7*inch, (y+.47)*inch, left_label)
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(1.7*inch, (y+.1)*inch, str(left_value))

        # total card
        self.c.setFillColor(HexColor(f'{self.card_color}95', hasAlpha=True))
        self.c.roundRect(3.15*inch, (y-.1)*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(4.25*inch, (y+.47)*inch, 'Records')
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(4.25*inch, (y+.1)*inch, str(total))

        # right status card
        self.c.setFillColor(HexColor(f'{right_color}3d', hasAlpha=True))
        self.c.roundRect(5.7*inch, (y-.1)*inch, 2.2*inch, .95*inch, .12*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(right_color))
        self.c.rect(5.7*inch, (y-.1)*inch, .1*inch, .95*inch, stroke=0, fill=1)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont('Helvetica', 10)
        self.c.drawCentredString(6.8*inch, (y+.47)*inch, right_label)
        self.c.setFont('Helvetica-Bold', 20)
        self.c.drawCentredString(6.8*inch, (y+.1)*inch, str(right_value))
        return y - .52



    def draw_collection_headers(self, data_type: str='issues', y: float=7.7) -> float:
        self.c.setFont('Helvetica-Bold', 10)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(.7*inch, y*inch, 'Time')
        self.c.drawString(2.45*inch, y*inch, 'Title')
        self.c.drawString(5.8*inch, y*inch, 'Details')
        return y - .22



    def create_collection_data(self, data_type: str) -> None:
        title_map = {
            'issues': 'Issues',
            'tests': 'Tests',
            'caseruns': 'Case Runs',
        }
        page_title = title_map.get(data_type, data_type.capitalize())
        rows = self.get_collection_rows(data_type=data_type)

        self.setup_page()
        self.draw_page_title(page_title)
        y = self.draw_collection_summary(rows=rows, data_type=data_type, y=7.55)
        y = self.draw_collection_headers(data_type=data_type, y=6.65)

        if len(rows) == 0:
            self.c.setFont('Helvetica', 11)
            self.c.setFillColor(HexColor(self.text_color))
            self.c.drawString(.65*inch, 7.2*inch, 'No records found in the selected lookback window.')
            self.end_page()
            return None

        row_height = .28
        for row in rows:
            if y < 1:
                self.end_page()
                self.setup_page()
                self.draw_page_title(f'{page_title} (continued)')
                y = self.draw_collection_summary(rows=rows, data_type=data_type, y=7.55)
                y = self.draw_collection_headers(data_type=data_type, y=6.65)

            status_color = self.get_status_color(str(row.get('bucket', '-')))

            # row body with leading color tab like audit rows
            self.c.setFillColor(HexColor(f'{self.highlight_color}95', hasAlpha=True))
            self.c.rect(.5*inch, (y-.10)*inch, 7.5*inch, .22*inch, stroke=0, fill=1)
            self.c.setFillColor(HexColor(status_color))
            self.c.rect(.5*inch, (y-.10)*inch, .08*inch, .22*inch, stroke=0, fill=1)

            self.c.setFillColor(HexColor(self.text_color))
            self.c.setFont('Helvetica', 9)
            self.c.drawString(.7*inch, (y-self.y_marg)*inch, self.format_dt(row.get('time'))[:20])
            self.c.drawString(2.45*inch, (y-self.y_marg)*inch, str(row.get('title', '-'))[:49])
            self.c.drawString(5.8*inch, (y-self.y_marg)*inch, str(row.get('detail', '-'))[:32])
            y -= row_height

        self.end_page()
        return None




    def create_data(self, data_type: str) -> None:
        """ 
        Paints the data for the passed 'data_type', 
        either 'lighthouse' or 'security'.
        
        Args:
            'data_type': str

        Returns:
            None
        """
        
        # add summary page first
        self.create_audit_summary_page(data_type=data_type)
        self.setup_page()
        
        # decide on which data type
        if data_type == 'security':
            data = self.scan.security
            data['audits'] = self.get_audits(data['audits'])
            page_title = 'Security'
            avg_score = 'average'

        if data_type == 'lighthouse':
            data = self.scan.lighthouse
            data['audits'] = self.get_audits(data['audits'])
            page_title = 'Lighthouse'
            avg_score = 'average'
            
        self.draw_page_title(page_title)
        if data['scores'][avg_score] is None:
            self.c.setFont('Helvetica', 11)
            self.c.setFillColor(HexColor(self.text_color))
            self.c.drawCentredString(4.25*inch, 8.7*inch, 'Latest audit data is unavailable for this section.')
            self.end_page()
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

                # catching unwanted categories 
                if cat in self.ignore_cats:
                    continue

                # creating global score
                if c_count == 0:
                    grade_obj = self.get_score_data((data['scores'][avg_score] or 0))
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
                        f'{data["scores"][avg_score]}'
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
                grade_obj = self.get_score_data((data['scores'][cat] or 0))
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
                    if data_type == 'security':
                        normal_score = self.normalize_score(policy["score"])
                        policy_text = policy["title"]
                        policy_value = f'{normal_score}%' if normal_score else ''
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
                        grade_obj = self.get_score_data(self.normalize_score(policy['score']), is_binary=binary)
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

        Returns:
            'report' : object,
            'success': bool,
            'message': str
        """

        # setting defaults
        message = 'Scan Page first'
        success = False

        report_types = self.get_report_types()
        has_audit_data = ('lighthouse' in report_types or 'security' in report_types or 'full' in report_types)
        has_collection_data = ('issues' in report_types or 'tests' in report_types or 'caseruns' in report_types or 'full' in report_types)

        # generating if at least one requested data source can be rendered
        if self.scan or has_collection_data:
            # add title
            self.cover_page()

            # build lighthouse data (latest audit + lookback summary)
            if ('lighthouse' in report_types or 'full' in report_types) and self.scan:
                self.create_data(data_type='lighthouse')

            # build security data (latest audit + lookback summary)
            if ('security' in report_types or 'full' in report_types) and self.scan:
                self.create_data(data_type='security')

            # build lookback sections
            if 'issues' in report_types or 'full' in report_types:
                self.create_collection_data(data_type='issues')
            if 'tests' in report_types or 'full' in report_types:
                self.create_collection_data(data_type='tests')
            if 'caseruns' in report_types or 'full' in report_types:
                self.create_collection_data(data_type='caseruns')

            # save report
            self.publish_report()
            message = 'Report Generated'
            if has_audit_data and not self.scan:
                message = 'Report Generated (latest scan unavailable for audit sections)'
            success = True
        
        # formating response
        data = {
            'report' : self.report,
            'success': success,
            'message': message
        }

        # returning response
        return data


        



    
