from ..models import *
from datetime import datetime
from .image import Image
from scanerr import settings
from difflib import SequenceMatcher, HtmlDiff, Differ
import time, os, sys, json, random, string, re, requests, uuid, boto3




class Tester():

    def __init__(self, test):
        self.test = test
        self.pre_scan_html = []
        self.post_scan_html = []
        self.pre_scan_logs = []
        self.post_scan_logs = []
        self.delta_html_post = []
        self.delta_html_pre = []

        # setup boto3 configurations
        self.s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )


    def clean_html(self):
        pre_scan_html_raw = requests.get(self.test.pre_scan.html).text
        post_scan_html_raw = requests.get(self.test.post_scan.html).text
        pre_scan_html = pre_scan_html_raw.splitlines()
        post_scan_html = post_scan_html_raw.splitlines()

        white_list = ['csrfmiddlewaretoken', '<!DOCTYPE html>',]
        tags = [
            '<head', '<script', '<div', '<p', '<h1', '<wbr', '<ul', '<tr', '<u', '<title', '<iframe',  
            '<section', '<source', '<style', '<q', '<option', '<nav', '<menu', '<mark', '<map', '<meta', '<keygen', '<link',
            '<li', '<legend', '<label', '<input', '<img', '<i', '<hr', '<hgroup', '<h2', '<h3', '<h4', '<h5', '<h6', '<form', 
            '<footer', '<figure', '<fieldset', '<embed', '<em', '<dt', '<dl', '<dialog', '<dfn', '<details', '<del', '<dd', 
            '<datalist', '<data', '<colgroup', '<col', '<code', '<cite', '<caption', '<canvas', '<button', '<body', '<blockquote',
            '<bdo', '<bdi', '<base', '<pre', '<b', '<br', '<audio', '<aside', '<article', '<area', '<address', '<abbr', '<a',
            '<!DOCTYPE html>', '</head', '</script', '</div', '</p', '</h1', '</wbr', '</ul', '</tr', '</u', '</title', '</iframe',  
            '</section', '</source', '</style', '</q', '</option', '</nav', '</menu', '</mark', '</map', '</meta', '</keygen', '</link',
            '</li', '</legend', '</label', '</input', '</img', '</i', '</hr', '</hgroup', '</h2', '</h3', '</h4', '</h5', '</h6', '</form', 
            '</footer', '</figure', '</fieldset', '</embed', '</em', '</dt', '</dl', '</dialog', '</dfn', '</details', '</del', '</dd', 
            '</datalist', '</data', '</colgroup', '</col', '</code', '</cite', '</caption', '</canvas', '</button', '</body', '</blockquote',
            '</bdo', '</bdi', '</base', '</pre', '</b', '</br', '</audio', '</aside', '</article', '</area', '</address', '</abbr', '</a',
        ]
        for line in pre_scan_html:
            for item in white_list:
                if item in line:
                    pre_scan_html.remove(line)
        for line in pre_scan_html:
            new_line = line.replace('\t', '').replace('\\', '').replace('"\"', '')
            subStrings = re.split('>', new_line)
            for sub in subStrings:
                if sub not in tags:
                    self.pre_scan_html.append((sub+'>'))
        
        for line in post_scan_html:
            for item in white_list:
                if item in line:
                    post_scan_html.remove(line)
        for line in post_scan_html:
            new_line = line.replace('\t', '').replace('\\', '').replace('"\"', '')
            subStrings = re.split('>', new_line)
            for sub in subStrings:
                if sub not in tags:
                    self.post_scan_html.append((sub+'>'))

        return

    
    def clean_logs(self): 
        pre_scan_logs_json = self.test.pre_scan.logs
        post_scan_logs_json = self.test.post_scan.logs
        order = ("level", "source", "message")


        for log in pre_scan_logs_json:
            new_log = {}
            for label in order:
                for key in log:
                    if key == label:
                        new_log[label] = log.get(key)
            self.pre_scan_logs.append(json.dumps(new_log))


        for log in post_scan_logs_json:
            new_log = {}
            for label in order:
                for key in log:
                    if key == label:
                        new_log[label] = log.get(key)
            self.post_scan_logs.append(json.dumps(new_log))

        return


    def compare_html(self):
        self.clean_html()
        pre_scan = self.pre_scan_html
        post_scan = self.post_scan_html
        html_raw_score = SequenceMatcher(
            None, pre_scan, post_scan
        ).ratio()

        return html_raw_score



    def compare_logs(self):
        self.clean_logs()
        pre_scan = list(self.pre_scan_logs)
        post_scan = list(self.post_scan_logs)
        logs_raw_score = SequenceMatcher(
            None, pre_scan, post_scan
        ).ratio()

        return logs_raw_score


    def delta_html(self):
        num_html_delta = len(self.pre_scan_html) - len(self.post_scan_html)
        num_html_ratio = len(self.pre_scan_html) / len(self.post_scan_html)
        if num_html_ratio > 1:
            num_html_ratio = len(self.post_scan_html) / len(self.pre_scan_html)
        
        for line in self.post_scan_html:
            if line not in self.pre_scan_html:
                self.delta_html_post.append(line)

        for line in self.pre_scan_html:
            if line not in self.post_scan_html:
                self.delta_html_pre.append(line)


        pre_micro_delta = self.post_proc_html(
            self.delta_html_pre, 
            self.delta_html_post
        )

        post_micro_delta = self.post_proc_html(
            self.delta_html_post, 
            self.delta_html_pre
        )
            
    
        data = {
            "num_html_delta": num_html_delta,
            "delta_html_post": self.delta_html_post,
            "delta_html_pre": self.delta_html_pre,
            "num_html_ratio": num_html_ratio,
            "pre_micro_delta": pre_micro_delta,
            "post_micro_delta": post_micro_delta,
        }

        return data


    def post_proc_html(self, primary_list, secondary_list):
        delta_parsed = []
        delta_parsed_diff = []
        secondary_str = ''.join(str(i) for i in secondary_list)

        # breaking html elements into small 8 chars chunks
        for line in primary_list:
            subStrings = re.findall('.{1,8}', line)
            for sub in subStrings:
                delta_parsed.append(sub)

        # checking if small chunk is in other scan
        for block in delta_parsed:
            if block != None and block != '' and block not in secondary_str:
                delta_parsed_diff.append(block)

        data = {
            "delta_parsed": delta_parsed,
            "delta_parsed_diff": delta_parsed_diff,
        }

        return data




    def html_micro_diff_score(self, post_delta_parsed_diff):

        pre_delta_parsed_diff = []
        for line in self.pre_scan_html:
            subStrings = re.findall('.{1,8}', line)
            for sub in subStrings:
                pre_delta_parsed_diff.append(sub)

        diff_length = len(pre_delta_parsed_diff) - len(post_delta_parsed_diff)
        diff_score = diff_length / len(pre_delta_parsed_diff)

        return diff_score

    

    
    def post_proc_logs(self, log):
        log = json.loads(log)
        log["message"].replace("\"", "\'")        
        letters = string.digits
        timestamp = ''.join(random.choice(letters) for i in range(13))
        log['timestamp'] = timestamp

        return log

       


    def delta_logs(self):
        num_logs_delta = len(self.pre_scan_logs) - len(self.post_scan_logs)

        if len(self.post_scan_logs) > 0:
            num_logs_ratio = len(self.pre_scan_logs) / len(self.post_scan_logs)
            if num_logs_ratio > 1:
                num_logs_ratio = 1
        else:
            num_logs_ratio = 1
        
        delta_logs_post = []
        for log in self.post_scan_logs:
            if log not in self.pre_scan_logs:
                log = self.post_proc_logs(log)
                delta_logs_post.append(log)


        delta_logs_pre = []
        for log in self.pre_scan_logs:
            if log not in self.post_scan_logs:
                log = self.post_proc_logs(log)
                delta_logs_pre.append(log)

        data = {
            "num_logs_delta": num_logs_delta,
            "delta_logs_post": delta_logs_post,
            "delta_logs_pre": delta_logs_pre,
            "num_logs_ratio": num_logs_ratio,
        }

        return data





    def delta_lighthouse(self):
        try:
            pre_seo = int(self.test.pre_scan.lighthouse["scores"]['seo'])
            pre_accessibility = int(self.test.pre_scan.lighthouse["scores"]['accessibility'])
            pre_performance = int(self.test.pre_scan.lighthouse["scores"]['performance'])
            pre_best_practices = int(self.test.pre_scan.lighthouse["scores"]['best_practices'])
            pre_pwa = int(self.test.pre_scan.lighthouse["scores"]['pwa'])
            
            post_seo = int(self.test.post_scan.lighthouse["scores"]['seo'])
            post_accessibility = int(self.test.post_scan.lighthouse["scores"]['accessibility'])
            post_performance = int(self.test.post_scan.lighthouse["scores"]['performance'])
            post_best_practices = int(self.test.post_scan.lighthouse["scores"]['best_practices'])
            post_pwa = int(self.test.post_scan.lighthouse["scores"]['pwa'])

            try:
                pre_crux = int(self.test.pre_scan.lighthouse["scores"]['crux'])
                post_crux = int(self.test.post_scan.lighthouse["scores"]['crux'])
                crux_delta = post_crux - pre_crux
            except:
                pre_crux = None
                post_crux = None
                crux_delta = 0

            seo_delta = post_seo - pre_seo
            accessibility_delta = post_accessibility - pre_accessibility 
            performance_delta = post_performance - pre_performance
            best_practices_delta = post_best_practices - pre_best_practices
            pwa_delta = post_pwa - pre_pwa
            
            if post_crux is None:
                current_average = (
                    post_seo + post_accessibility + post_best_practices + 
                    post_performance + post_pwa 
                )/5
                
                old_average = (
                    pre_seo + pre_accessibility + pre_best_practices + 
                    pre_performance + pre_pwa 
                )/5
            
            else:
                current_average = (
                    post_seo + post_accessibility + post_best_practices + 
                    post_performance + post_pwa + post_crux
                )/6
                
                old_average = (
                    pre_seo + pre_accessibility + pre_best_practices + 
                    pre_performance + pre_pwa + pre_crux
                )/6

            average_delta = current_average - old_average 

        except:
            seo_delta = None
            accessibility_delta = None 
            performance_delta = None
            best_practices_delta = None
            pwa_delta = None
            crux_delta = None
            current_average = None
            average_delta = None

        data = {
            "scores": {
                "seo_delta": seo_delta,
                "accessibility_delta": accessibility_delta,
                "performance_delta": performance_delta,
                "best_practices_delta": best_practices_delta,
                "pwa_delta": pwa_delta,
                "crux_delta": crux_delta,
                "current_average": current_average,
                "average_delta": average_delta,
            }
        }

        return data






    def delta_yellowlab(self):
        try:
            pre_globalScore = int(self.test.pre_scan.yellowlab["scores"]['globalScore'])
            pre_pageWeight = int(self.test.pre_scan.yellowlab["scores"]['pageWeight'])
            pre_requests = int(self.test.pre_scan.yellowlab["scores"]['requests'])
            pre_domComplexity = int(self.test.pre_scan.yellowlab["scores"]['domComplexity'])
            pre_javascriptComplexity = int(self.test.pre_scan.yellowlab["scores"]['javascriptComplexity'])
            pre_badJavascript = int(self.test.pre_scan.yellowlab["scores"]['badJavascript'])
            pre_jQuery = int(self.test.pre_scan.yellowlab["scores"]['jQuery'])
            pre_cssComplexity = int(self.test.pre_scan.yellowlab["scores"]['cssComplexity'])
            pre_badCSS = int(self.test.pre_scan.yellowlab["scores"]['badCSS'])
            pre_fonts = int(self.test.pre_scan.yellowlab["scores"]['fonts'])
            pre_serverConfig = int(self.test.pre_scan.yellowlab["scores"]['serverConfig'])

            post_globalScore = int(self.test.post_scan.yellowlab["scores"]['globalScore'])
            post_pageWeight = int(self.test.post_scan.yellowlab["scores"]['pageWeight'])
            post_requests = int(self.test.post_scan.yellowlab["scores"]['requests'])
            post_domComplexity = int(self.test.post_scan.yellowlab["scores"]['domComplexity'])
            post_javascriptComplexity = int(self.test.post_scan.yellowlab["scores"]['javascriptComplexity'])
            post_badJavascript = int(self.test.post_scan.yellowlab["scores"]['badJavascript'])
            post_jQuery = int(self.test.post_scan.yellowlab["scores"]['jQuery'])
            post_cssComplexity = int(self.test.post_scan.yellowlab["scores"]['cssComplexity'])
            post_badCSS = int(self.test.post_scan.yellowlab["scores"]['badCSS'])
            post_fonts = int(self.test.post_scan.yellowlab["scores"]['fonts'])
            post_serverConfig = int(self.test.post_scan.yellowlab["scores"]['serverConfig'])

            pageWeight_delta = post_pageWeight - pre_pageWeight
            requests_delta = post_requests - pre_requests
            domComplexity_delta = post_domComplexity - pre_domComplexity
            javascriptComplexity_delta = post_javascriptComplexity - pre_javascriptComplexity
            badJavascript_delta = post_badJavascript - pre_badJavascript
            jQuery_delta = post_jQuery - pre_jQuery
            cssComplexity_delta = post_cssComplexity - pre_cssComplexity
            badCSS_delta = post_badCSS - pre_badCSS
            fonts_delta = post_fonts - pre_fonts
            serverConfig_delta = post_serverConfig - pre_serverConfig 

            average_delta = post_globalScore - pre_globalScore 
            current_average = post_globalScore

        except:
            pageWeight_delta = None
            requests_delta = None
            domComplexity_delta = None
            javascriptComplexity_delta = None
            badJavascript_delta = None
            jQuery_delta = None
            cssComplexity_delta = None
            badCSS_delta = None
            fonts_delta = None
            serverConfig_delta = None 
            average_delta = None
            current_average = None,

        data = {
            "scores": {
                "pageWeight_delta": pageWeight_delta, 
                "requests_delta": requests_delta, 
                "domComplexity_delta": domComplexity_delta, 
                "javascriptComplexity_delta": javascriptComplexity_delta,
                "badJavascript_delta": badJavascript_delta,
                "jQuery_delta": jQuery_delta,
                "cssComplexity_delta": cssComplexity_delta,
                "badCSS_delta": badCSS_delta,
                "fonts_delta": fonts_delta,
                "serverConfig_delta": serverConfig_delta,
                "average_delta": average_delta,
                "current_average": current_average,
            }
        }

        return data



    def update_site_info(self, test):
        site = test.site

        # get pages
        pages = Page.objects.filter(site=site)

        # get latest tests of pages
        tests = []
        for page in pages:
            if Test.objects.filter(page=page).exists():
                _test = Test.objects.filter(page=page).order_by('-time_completed')[0]
                if _test.score is not None:
                    tests.append(_test.score)
        
        if len(tests) > 0:
            # calc site average of latest
            site_avg_test_score = round((sum(tests)/len(tests)) * 100) / 100

            site.info['latest_test']['id'] = str(test.id)
            site.info['latest_test']['time_created'] = str(test.time_created)
            site.info['latest_test']['time_completed'] = str(test.time_completed)
            site.info['latest_test']['score'] = site_avg_test_score
            site.save()

        return site



    def update_page_info(self, test):
        page = test.page
        page.info['latest_test']['id'] = str(test.id)
        page.info['latest_test']['time_created'] = str(test.time_created)
        page.info['latest_test']['time_completed'] = str(test.time_completed)
        page.info['latest_test']['score'] = (round(test.score * 100) / 100)
        page.save()

        return page
        



    def run_test(self, index=None):

        # update test obj with scan configs
        self.test.pre_scan_configs = self.test.pre_scan.configs
        self.test.post_scan_configs = self.test.post_scan.configs
        self.test.save()

        # default scores 
        html_score = 0
        num_html_ratio = 0
        micro_diff_score = 0
        logs_score = 0
        num_logs_ratio = 0
        lighthouse_score = 0
        yellowlab_score = 0
        images_score = 0

        # default weights
        html_score_w = 0
        num_html_w = 0
        micro_diff_w = 0
        logs_score_w = 0
        num_logs_w = 0
        delta_lh_w = 0
        delta_yl_w = 0
        images_w = 0

        # default data
        html_delta_context = None
        html_delta_uri = None
        logs_delta_context = None
        lighthouse_data = None
        yellowlab_data = None
        images_data = None



        if 'html' in self.test.type or 'full' in self.test.type:
            try:
                # scores
                html_score = self.compare_html()
                delta_html_data = self.delta_html()
                num_html_ratio = delta_html_data['num_html_ratio']
                micro_diff_score = self.html_micro_diff_score(
                    delta_html_data['post_micro_delta']['delta_parsed_diff']
                )
                
                # weights
                html_score_w = 1
                num_html_w = 1
                micro_diff_w = 2
                
                # data
                html_delta_context = {
                    "pre_html_delta": delta_html_data['delta_html_pre'],
                    "post_html_delta": delta_html_data['delta_html_post'],
                    "pre_micro_delta": delta_html_data['pre_micro_delta'],
                    "post_micro_delta": delta_html_data['post_micro_delta'],
                }

                # save html_delta s3 json file
                file_id = uuid.uuid4()
                with open(f'{file_id}.json', 'w') as fp:
                    json.dump(html_delta_context, fp)
                
                # upload to s3 and return url
                html_delta_file = os.path.join(settings.BASE_DIR, f'{file_id}.json')
                remote_path = f'static/sites/{self.test.site.id}/{self.test.page.id}/{self.test.id}/{file_id}.json'
                root_path = settings.AWS_S3_URL_PATH
                html_delta_uri = f"{root_path}/{remote_path}"
            
                # upload to s3
                with open(html_delta_file, 'rb') as data:
                    self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                        remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "application/json"}
                    )
                # remove local copy
                os.remove(html_delta_file)

                print(f'html_delta => {html_delta_uri}')

            except Exception as e:
                print(e)
        
        

        if 'logs' in self.test.type or 'full' in self.test.type:
            try:
                # scores
                logs_score = self.compare_logs()
                delta_logs_data = self.delta_logs()
                num_logs_ratio = delta_logs_data['num_logs_ratio']
                
                # weights
                logs_score_w = .5
                num_logs_w = 2

                # data
                logs_delta_context = {
                    "pre_logs_delta": delta_logs_data['delta_logs_pre'],
                    "post_logs_delta": delta_logs_data['delta_logs_post'],
                }
            except Exception as e:
                print(e)



        if 'lighthouse' in self.test.type or 'full' in self.test.type:
            try:
                # scores & data
                lighthouse_data = self.delta_lighthouse()
                lighthouse_avg = lighthouse_data['scores']['average_delta']
                if lighthouse_avg != None and lighthouse_avg > -100:
                    lighthouse_score = (100 + lighthouse_avg)/100
                if lighthouse_avg != None and lighthouse_avg <= -100:
                    lighthouse_score = 0

                # weights
                if lighthouse_score == None:
                    delta_lh_w = 0
                elif lighthouse_score > 1:
                    delta_lh_w = 1
                    lighthouse_score = 1
                else:
                    delta_lh_w = 1
            except Exception as e:
                print(e)


        

        if 'yellowlab' in self.test.type or 'full' in self.test.type:
            try:
                # scores & data
                yellowlab_data = self.delta_yellowlab()
                yellowlab_avg = yellowlab_data['scores']['average_delta']
                if yellowlab_avg != None and yellowlab_avg > -100:
                    yellowlab_score = (100 + yellowlab_avg)/100
                if yellowlab_avg != None and yellowlab_avg <= -100:
                    yellowlab_score = 0

                # weights
                if yellowlab_score == None:
                    delta_yl_w = 0
                elif yellowlab_score > 1:
                    delta_yl_w = 1
                    yellowlab_score = 1
                else:
                    delta_yl_w = 1
            except Exception as e:
                print(e)




        if 'vrt' in self.test.type or 'full' in self.test.type:
            try:
                # scores & data
                images_data = Image().test(test=self.test, index=index)
                if images_data['average_score'] != None:
                    images_score = images_data['average_score'] / 100

                # weights
                images_w = 4
            except Exception as e:
                    print(e)
        
        

        total_w = (
            html_score_w + logs_score_w + num_html_w 
            + num_logs_w + delta_lh_w + micro_diff_w
            + images_w + delta_yl_w
        )
        
        
        score = ((
            (html_score * html_score_w) + 
            (logs_score * logs_score_w) + 
            (num_logs_ratio * num_logs_w) + 
            (num_html_ratio * num_html_w) +
            (lighthouse_score * delta_lh_w) + 
            (yellowlab_score * delta_yl_w) +
            (micro_diff_score * micro_diff_w) +
            (images_score * images_w)
        ) / total_w) * 100

        
        print(
            "Formula was --> ((" + str(html_score*html_score_w) + " + " 
            + str(logs_score*logs_score_w) + " + " + str(num_logs_ratio*num_logs_w) + " + " 
            + str(num_html_ratio*num_html_w) +  " + " + str(lighthouse_score*delta_lh_w) + 
            " + " + str(micro_diff_score*micro_diff_w) + " + " + str(images_score * images_w)+
            " + " + str(yellowlab_score*delta_yl_w) + ") / " + str(total_w) + ") * 100 ===> " + str(score)
        )


        self.test.time_completed = datetime.now()
        self.test.html_delta = html_delta_uri
        self.test.logs_delta = logs_delta_context
        self.test.lighthouse_delta = lighthouse_data
        self.test.yellowlab_delta = yellowlab_data
        self.test.images_delta = images_data
        self.test.score = score
        self.test.component_scores['html'] = (micro_diff_score * 100)
        self.test.component_scores['logs'] = (num_logs_ratio * 100)
        self.test.component_scores['lighthouse'] = (lighthouse_score * 100)
        self.test.component_scores['yellowlab'] = (yellowlab_score * 100)
        self.test.component_scores['vrt'] = (images_score * 100)


        self.test.save()

        self.update_page_info(self.test)
        self.update_site_info(self.test)

        return self.test







