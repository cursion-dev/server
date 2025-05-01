from ..models import *
from cursion import settings
from openai import OpenAI
from .meter import meter_account
import time, os, json, uuid, \
    random, boto3, re, requests, \
    tiktoken






class Issuer():
    """ 
    Generate new `Issue` for the passed 'test' or 'caserun'.

    Expects: {
        'scan'      : object
        'test'      : object,
        'caserun'   : object,
        'threshold' : int
    }

    Use `Issuer.build_issue()` to generate new `Issue`

    Returns -> None
    """




    def __init__(
            self,
            scan        : object=None, 
            test        : object=None,
            caserun     : object=None,
            threshold   : int=75
        ):
         
        # main objects
        self.scan       = scan
        self.test       = test
        self.caserun    = caserun
        self.object     = None
        self.type       = None
        self.threshold  = test.threshold if test else threshold

        # top level vars
        self.title      = None
        self.details    = None
        self.data       = None
        self.labels     = None
        self.account    = None
        self.trigger    = { 'type': None, 'id': None }
        self.affected   = { 'type': None, 'id': None, 'str': None}
        self.max_len    = 200
        self.max_tokens = 5000
        self.gpt_model  = "gpt-4o-mini"
        
        # init GPT client
        self.gpt_client = OpenAI(
            api_key=settings.GPT_API_KEY,
        )




    def convert_key(self, key: str=None) -> str:
        """ 
        Converts the passed camel case or 
        snake case str into a spaced str with 
        each word capitalized

        Expects: {
            key: str
        }

        Returns -> str
        """

        # remove "_delta"
        key = key.replace('_delta', '')

        # convert from camelCase
        key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)

        # convert snake_case
        key = key.replace('_', ' ')

        # capitalize
        key = key.title()

        return key


    

    def clean_recommendation(self, recommendation: str=None) -> str:
        """ 
        Replaces URLs with correct URLs

        Expects: {
            'recommendation': str
        }

        Returns -> str
        """
        # clean client URI
        client_uri = settings.CLIENT_URL_ROOT.split('://')[1]

        # repalce URI
        recommendation = recommendation.replace(
            'localhost', 
            client_uri
        )

        # return clean recommendation
        return recommendation




    def build_issue(self):
        """ 
        Creates a new `Issue` based on the info 
        from the passed "self.test" or "self.caserun"

        Expects: None

        Returns -> `Issue` <obj>
        """

        # deciding on type
        self.obj = self.scan or self.test or self.caserun
        self.type = 'scan' if self.scan else 'test' if self.test else 'caserun'

        # define account
        self.account = self.obj.site.account

        # update triggers & affected
        self.trigger = {
            'type'  : self.type, 
            'id'    : str(self.obj.id)
        }
        self.affected = {
            'type'  : 'site' if self.caserun else 'page',
            'id'    : str(self.obj.site.id) if self.caserun else str(self.obj.page.id),
            'str'   : self.obj.site.site_url if self.caserun else self.obj.page.page_url
        }

        # building details, title, & recomemdations
        # for Scan performance & log data
        if self.scan:
            self._handle_scan()
        
        # building details, title, & 
        # recomemdations for test failure
        if self.test:
            self._handle_test()
            
        # building details, title, & 
        # recomemdations for caserun failure
        if self.caserun:
            self._handle_caserun()

        # build recommendation
        response = self.build_recommendation()

        recommendation = str(
            f'\n\n### Recommendations:\n' +
            f'{response}'
        )
        
        # clean recommendation
        recommendation = self.clean_recommendation(recommendation)

        # build details from components
        self.details = self.details + recommendation

        # creating new Issue
        issue = Issue.objects.create(
            account  = self.account,
            title    = self.title,
            details  = self.details,
            labels   = self.labels, 
            trigger  = self.trigger,
            affected = self.affected
        )

        # meter account if necessary
        if self.account.type == 'cloud' and self.account.cust_id:
            meter_account(str(self.account.id), 1)
        
        # new Issue
        return issue




    def _handle_scan(self) -> None:
        """ 
        Handles data collection for a scan

        Expects: None

        Returns: None
        """

        # defaults for data categorization
        cats    = []
        comps   = []
        lh      = []
        yl      = []
        logs    = []

        # get raw audits
        lh_audits = requests.get(self.scan.lighthouse.get('audits')).json() if self.scan.lighthouse.get('audits') else ''
        yl_audits = requests.get(self.scan.yellowlab.get('audits')).json() if self.scan.yellowlab.get('audits') else ''

        # include logs
        if self.scan.logs:
            if len(self.scan.logs) > 0:
                cats.append({
                    'key'   : 'logs',
                    'name'  : 'Console Issues',
                    'value' : str(len(self.scan.logs))
                })
                comps.append('Console')
                logs = self.scan.logs

        # include lighthouse 
        if self.scan.lighthouse.get('audits'):
            for key in self.scan.lighthouse.get('scores'):
                if key != 'average' and key != 'crux':
                    if int(self.scan.lighthouse.get('scores')[key]) < self.threshold:
                        # include LH categories
                        cats.append({
                            'key'   : key,
                            'name'  : f"{self.convert_key(key)} (lighthouse)",
                            'value' : f"{self.scan.lighthouse.get('scores')[key]}%"
                        }) 
                        # update str for title
                        if not any('Performance' in i for i in comps):
                            comps.append('& Performance' if 'Console' in comps else 'Performance')
                        # save audits
                        lh.append({
                            key: lh_audits.get(key)
                        })

        # include yellowlab 
        if self.scan.yellowlab.get('audits'):
            for key in self.scan.yellowlab.get('scores'):
                if key != 'globalScore':
                    if int(self.scan.yellowlab.get('scores')[key]) < self.threshold:
                        # include YL categories
                        cats.append({
                            'key'   : key,
                            'name'  : f"{self.convert_key(key)} (yellowlab)",
                            'value' : f"{self.scan.yellowlab.get('scores')[key]}%"
                        })
                        # update str for title
                        if not any('Performance' in i for i in comps):
                            comps.append('& Performance' if 'Console' in comps else 'Performance')
                        # save audits
                        yl.append({
                            key: yl_audits.get(key)
                        })

        # build title
        self.title = f'Scan found {' '.join(comps)} Issues'

        # build intro
        intro = str(
            f'## This [Scan]({settings.CLIENT_URL_ROOT}/{self.trigger["type"]}/{self.trigger["id"]}) ' +
            f'contains {' '.join(comps)} issues.\n' +
            f'\n\n> Affected Page ' + 
            f'[{self.affected["str"]}]({settings.CLIENT_URL_ROOT}/{self.affected["type"]}/{self.affected["id"]}) \n\n' 
        )

        # build components str
        comp_str = str('| Component | Value |\n|:-----|-----:|')
        for item in cats:
            comp_str += f'\n| {item.get('name')} | {item.get('value')} |'

        # build main_issue
        main_issue = str(
            f'### Failing Components:\n' + 
            f'{comp_str}'
        )

        # combine into details
        self.details = str(intro + main_issue)

        # build & format data for AI
        self.data = f'\n\n------------\n\n'
        if len(logs) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nBrowser Console Errors and Warnings:' +
                f'\n{logs}'
            )
        if len(lh) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nAudit data from Google Lighthouse:' +
                f'\n{lh}'
            )
        if len(yl) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nAudit data from YellowLab Tools:' +
                f'\n{yl}'
            )
        self.data += f'\n\n------------\n\n'




    def _handle_test(self) -> None:
        """ 
        Handles data collection for a test

        Expects: None

        Returns: None
        """

        # defaults
        lh        = []
        yl        = []
        logs      = []
        vrt       = {}
        lh_audits = ''
        yl_audits = ''

        # get post_logs_delta
        logs = self.test.logs_delta.get('post_logs_delta') if self.test.logs_delta else []

        # get raw audits
        if self.test.lighthouse_delta:
            lh_audits = requests.get(self.test.lighthouse_delta.get('audits')).json() if self.test.lighthouse_delta.get('audits') else ''
        if self.test.yellowlab_delta:
            yl_audits = requests.get(self.test.yellowlab_delta.get('audits')).json() if self.test.yellowlab_delta.get('audits') else ''

        # record only audits from LH components
        # that had negative scores
        if self.test.lighthouse_delta.get('audits'):
            if self.test.component_scores.get('lighthouse') < self.threshold:
                for key in self.test.lighthouse_delta.get('scores'):
                    if 'average' not in key and 'crux' not in key:
                        if self.test.lighthouse_delta.get('scores')[key] < 0:
                            key = key.replace('_delta', '')
                            lh.append({
                                key: lh_audits.get(key)
                            }) 
        
        # record only audits from YL components
        # that had negative scores
        if self.test.yellowlab_delta.get('audits'):
            if self.test.component_scores.get('yellowlab') < self.threshold:
                for key in self.test.yellowlab_delta.get('scores'):
                    if 'average' not in key:
                        if self.test.yellowlab_delta.get('scores')[key] < 0:
                            key = key.replace('_delta', '')
                            yl.append({
                                key: yl_audits.get(key)
                            }) 

        # record any information about VRT
        if 'vrt' in self.test.type:
            vrt['similarity_score'] = self.test.component_scores.get('vrt')
            vrt['summary'] = self.test.images_delta.get('summary')
            vrt['broken'] = self.test.images_delta.get('broken')

        # grabbing component scores
        # which were less than the test.threshold
        ordered_scores = []
        for key in self.test.component_scores:
            if self.test.component_scores[key] is not None:
                if self.test.component_scores[key] < self.test.threshold:
                    ordered_scores.append({key: self.test.component_scores[key]})

        # build components str
        comp_str = str('| Component | Score |\n|:-----|-----:|')
        for score in ordered_scores:
            for key in score:
                comp_str += f'\n| {key} | {round(score[key], 2)} |'

        # adjusting component names in table
        comp_str = comp_str.replace(
                'vrt', 
                'visual regression (vrt)'
            ).replace(
                'html', 
                'html regression (html)'
            )

        # build title
        self.title = f'Test Failed at {round(self.test.score, 2)}%'

        # build intro
        intro = str(
            f'## This [Test]({settings.CLIENT_URL_ROOT}/{self.trigger["type"]}/{self.trigger["id"]}) failed ' +  
            f'based on the set threshold of **{round(self.test.threshold, 2)}%**.\n' +
            f'\n\n> Affected Page ' + 
            f'[{self.affected["str"]}]({settings.CLIENT_URL_ROOT}/{self.affected["type"]}/{self.affected["id"]})\n\n'
        )

        # build main_issue
        main_issue = str(
            f'### Failing Components:\n' + 
            f'{comp_str}'
        )

        # combine into details
        self.details = str(intro + main_issue)

        # build & format data for AI
        self.data = f'\n\n------------\n\n'
        if len(logs) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nBrowser Console Errors and Warnings:' +
                f'\n{logs}'
            )
        if len(lh) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nAudit data from Google Lighthouse:' +
                f'\n{lh}'
            )
        if len(yl) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nAudit data from YellowLab Tools:' +
                f'\n{yl}'
            )
        if len(vrt) > 0:
            self.max_len += 50
            self.data += str(
                f'\n\n\nVisual Regression Data:' +
                f'\n{vrt}'
            )
        self.data += f'\n\n------------\n\n'




    def _handle_caserun(self) -> None:
        """ 
        Handles data collection for a caserun

        Expects: None

        Returns: None
        """
        # get first step that failed in caserun
        failed_step = None
        step_index = 0
        step_type = 'action'
        for step in self.caserun.steps:
            step_index += 1
            if step['action']['status'] == 'failed':
                failed_step = step
                step_type = 'action'
                break
            if step['assertion']['status'] == 'failed':
                failed_step = step
                step_type = 'assertion'
                break

        # build title
        self.title = f'Case Run "{self.caserun.title}" Failed'

        # build intro
        intro = str(
            f'## Case Run [{self.caserun.title}]({settings.CLIENT_URL_ROOT}/{self.trigger["type"]}/{self.trigger["id"]})' + 
            f' failed on **Step {step_index}**, `{failed_step[step_type]["type"]}`.\n\n\n' +
            f' > Affected Site: [{self.affected["str"]}]({settings.CLIENT_URL_ROOT}/{self.affected["type"]}/{self.affected["id"]})\n\n\n'
        )
        
        # build main_issue
        main_issue = str(
            f'### Main Issue or Exception:\n' + 
            f' ```shell\n{failed_step[step_type]["exception"]}\n``` \n\n' +
            f' [View Image]({failed_step[step_type]["image"]})\n\n'
        )

        # combine into details
        self.details = str(intro + main_issue)

        # no extra data yet 
        self.data = None




    def build_recommendation(self) -> str:
        """ 
        Using OpenAI's Chat GPT, composes a personalized 
        `recommendation` for the primary `Issue` being created. 

        Expects: None

        Returns -> str    
        """

        # initializing
        recommendation = ''

        # truncate self.data
        encoding = tiktoken.encoding_for_model(self.gpt_model)
        tokens = encoding.encode(self.data)
        if len(tokens) > self.max_tokens:
            tokens = tokens[:self.max_tokens]
        self.data = encoding.decode(tokens)

        # building recommendation
        # for self.scan
        if self.scan:
            
            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model=self.gpt_model, # old model -> gpt-3.5-turbo
                messages=[
                    {
                        "role": "user", 
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{self.details}\n\n'. \
                            Below is output data from the Scan to help you identify potential recommendations: {self.data} \
                            If possible, include reference to any files, scripts, images, etc. which should be addressed based on the provided data. \
                            Prioritize recommendations based on highest impact to the performance and security of the web page. \
                            Format each recommendation with markdown. \
                            Begin each recommendation with '- [ ]' to format as a task. \
                            Omit the title or header in your response. \
                            Omit any summary after the recommendations. \
                            Remove any disclaimer or note section. \
                            Remove any reference to 'Test Cases'. \
                            Remove and reference to 'visual comparison tools'. \
                            Max Length of Response: {self.max_len} words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content
        

        # building recommendation
        # for self.test
        if self.test:
            
            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{self.details}\n\n'. \
                            The components are portions of a regression test of a website. \
                            Below is output data from the Test to help you identify potential \
                            recommendations for performance, browser logs, and visual regressions: {self.data} \
                            If possible, include reference to any files, scripts, etc. \
                            which should be addressed based on the provided data. \
                            Format each recommendation with markdown. \
                            Begin each recommendation with '- [ ]' to format as a task. \
                            Omit the title or header in your response. \
                            Omit any summary after the recommendations. \
                            Remove any disclaimer or note section. \
                            Remove any reference to 'Test Cases'. \
                            Remove and reference to 'visual comparison tools'. \
                            Max Length of Response: {self.max_len} words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content

        
        # building recommendation
        # for self.caserun
        if self.caserun:

            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {
                        "role": "user", 
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{self.details}\n\n'. \
                            Format each recommendation with markdown. \
                            Begin each recommendation with '- [ ]' to format as a task. \
                            Omit any summary after the recommendations. \
                            Omit the title or header in your response. \
                            Omit any links in your response. \
                            Remove any disclaimer or notes section. \
                            Remove any reference to selenium documentation. \
                            Remove any reference of 'alternative selector strategies'. \
                            Max Length of Response: {self.max_len} words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content

        # return recommendation 
        return recommendation

    



