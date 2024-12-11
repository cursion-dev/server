from ..models import *
from cursion import settings
from openai import OpenAI
import time, os, json, uuid, random, boto3






class Issuer():
    """ 
    Generate new `Issue` for the passed 'test' or 'caserun'.

    Expects: {
        'test'    : object,
        'caserun' : object,
    }

    Use `Issuer.build_issue()` to generate new `Issue`

    Returns -> None
    """




    def __init__(
            self, 
            test: object=None,
            caserun: object=None,
        ):
         
        # main objects
        self.test = test
        self.caserun = caserun
        
        # init GPT client
        self.gpt_client = OpenAI(
            api_key=settings.GPT_API_KEY,
        )


    

    def build_issue(self):
        """ 
        Creates a new `Issue` based on the info 
        from the passed "self.test" or "self.caserun"

        Expects: None

        Returns -> `Issue` <obj>
        """

        # defining top level attrs
        title = None
        details = None
        labels = None
        account = self.test.page.account if self.test else self.caserun.account
        trigger = {
            'type': 'test' if self.test else 'caserun', 
            'id': str(self.test.id) if self.test else str(self.caserun.id)
        }
        affected = {
            'type': 'page' if self.test else 'site',
            'id': str(self.test.page.id) if self.test else str(self.caserun.site.id),
            'str': self.test.page.page_url if self.test else self.caserun.site.site_url
        }

        # defining detail components 
        intro = ''
        main_issue = ''
        recommendation = ''

        # building details, title, & labels 
        # for caserun failure
        if self.caserun:

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
            title = f'Case Run "{self.caserun.title}" Failed'

            # build intro
            intro = str(
                f'### Case Run [{self.caserun.title}]({settings.CLIENT_URL_ROOT}/{trigger["type"]}/{trigger["id"]})' + 
                f' failed on **Step {step_index}**, `{failed_step[step_type]["type"]}`.\n\n\n' +
                f' > Affected Site: [{affected["str"]}]({settings.CLIENT_URL_ROOT}/{affected["type"]}/{affected["id"]})\n\n\n'
            )
            
            # build main_issue
            main_issue = str(
                f'### Main Issue or Exception:\n' + 
                f' ```shell\n{failed_step[step_type]["exception"]}\n``` \n\n' +
                f' [View Image]({failed_step[step_type]["image"]})\n\n'
            )

            # build recommendation
            response = self.build_recommendation(
                details = str(intro + main_issue)
            )
            recommendation = str(
                f'\n\n### Recommendations:\n' +
                f'{response}'
            )

        # building details, title, & labels 
        # for test failure
        if self.test:

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
            title = f'Test Failed at {round(self.test.score, 2)}%'

            # build intro
            intro = str(
                f'[Test]({settings.CLIENT_URL_ROOT}/{trigger["type"]}/{trigger["id"]}) failed for the page ' + 
                f'[{affected["str"]}]({settings.CLIENT_URL_ROOT}/{affected["type"]}/{affected["id"]}) ' + 
                f'based on the set threshold of **{round(self.test.threshold, 2)}%**.\n\n\n'
            )

            # build main_issue
            main_issue = str(
                f'### Failing Components:\n' + 
                f'{comp_str}'
            )

            # build recommendation
            response = self.build_recommendation(
                details = str(intro + main_issue)
            )
            recommendation = str(
                f'\n\n### Recommendations:\n' +
                f'{response}'
            )
        
        # clean recommendation
        recommendation = recommendation.replace('localhost', 'app.cursion.dev')

        # build details from components
        details = intro + main_issue + recommendation

        # creating new Issue
        issue = Issue.objects.create(
            account  = account,
            title    = title,
            details  = details,
            labels   = labels, 
            trigger  = trigger,
            affected = affected
        )
        
        # new Issue
        return issue




    def build_recommendation(
            self, 
            details: str=None,
        ) -> str:
        """ 
        Using OpenAI's Chat GPT, composes a personalized 
        `recommendation` for the primary `Issue` being created. 

        Expcets: {
            'details' : str,
        }

        Returns -> str    
        """

        # initializing
        recommendation = ''

        # building recommendation
        # for self.test
        if self.test:
            
            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model="gpt-4o-mini", # old model -> gpt-3.5-turbo
                messages=[
                    {
                        "role": "user", 
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{details}\n\n'. \
                            The components are portions of a regression test of a website. \
                            Format each recommendation with markdown. \
                            Begin each recommendation with '- [ ]' to format as a task. \
                            Omit the title or header in your response. \
                            Remove any disclaimer or note section. \
                            Remove any reference to 'Test Cases'. \
                            Remove and reference to 'visual comparison tools'. \
                            Max Length of Response: 170 words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content
        
        # building recommendation
        # for self.caserun
        if self.caserun:

            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model="gpt-4o-mini", # old model -> gpt-3.5-turbo
                messages=[
                    {
                        "role": "user", 
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{details}\n\n'. \
                            Format each recommendation with markdown. \
                            Begin each recommendation with '- [ ]' to format as a task. \
                            Omit the title or header in your response. \
                            Omit any links in your response. \
                            Remove any disclaimer or notes section. \
                            Remove any reference to selenium documentation. \
                            Remove any reference of 'alternative selector strategies'. \
                            Max Length of Response: 170 words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content

        # return recommendation 
        return recommendation

    



