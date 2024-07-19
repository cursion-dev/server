from ..models import *
from scanerr import settings
from openai import OpenAI
import time, os, json, uuid, random, boto3






class Issuer():
    """ 
    Generate new `Issue` for the passed 'test' or 'testcase'.

    Expects: {
        'test'        : object,
        'testcase'    : object,
    }

    Use `Issuer.build_issue()` to generate new `Issue`

    Returns -> None
    """




    def __init__(
            self, 
            test: object=None,
            testcase: object=None,
        ):
         
        # main objects
        self.test = test
        self.testcase = testcase
        
        # init GPT client
        self.gpt_client = OpenAI(
            api_key=settings.GPT_API_KEY,
        )


    

    def build_issue(self):
        """ 
        Creates a new `Issue` based on the info 
        from the passed "self.test" or "self.testcase"

        Expects: None

        Returns -> `Issue` <obj>
        """

        # defining top level attrs
        title = None
        details = None
        labels = None
        account = self.test.page.account if self.test else self.testcase.account
        trigger = {
            'type': 'test' if self.test else 'testcase', 
            'id': str(self.test.id) if self.test else str(self.testcase.id)
        }
        affected = {
            'type': 'page' if self.test else 'site',
            'id': str(self.test.page.id) if self.test else str(self.testcase.site.id),
            'str': self.test.page.page_url if self.test else self.testcase.site.site_url
        }

        # defining detail components 
        intro = ''
        main_issue = ''
        recommendation = ''

        # building details, title, & labels 
        # for testcase failure
        if self.testcase:

            # get first step that failed in testcase
            failed_step = None
            step_index = 0
            for step in self.testcase.steps:
                step_index += 1
                if not step['action']['passed']:
                    failed_step = step
                    break

            # build title
            title = f'Testcase "{self.testcase.case_name}" Failed'

            # build intro
            intro = str(
                f'#### Testcase [{self.testcase.case_name}](/{trigger["type"]}/{trigger["id"]})' + 
                f' failed on **Step {step_index}**, `{failed_step["action"]["type"]}`.\n\n' +
                f' **Affected Site:** [{affected["str"]}](/{affected["type"]}/{affected["id"]})\n\n\n'
            )
            
            # build main_issue
            main_issue = str(
                f'### Main Issue or Exception:\n' + 
                f' ```shell\n{failed_step["action"]["exception"]}\n``` \n\n' +
                f' [View Image]({failed_step["action"]["image"]})\n\n'
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
                f'[Test](/{trigger["type"]}/{trigger["id"]}) failed for the page ' + 
                f'[{affected["str"]}](/{affected["type"]}/{affected["id"]}) ' + 
                f'based on the set threshold of {round(self.test.threshold, 2)}%.\n\n\n'
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

        # building recomendation
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
                            Format with markdown. \
                            Format each recommendation as a markdown task. \
                            Omit the title or header in your response. \
                            Remove any disclaimer or note section. \
                            Remove any reference to 'Test Cases'. \
                            Remove and reference to 'visual comparison tools'. \
                            Max Length of Response: 170 words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content
        
        # building recomendation
        # for self.testcase
        if self.testcase:

            # send the initial request
            recommendation = self.gpt_client.chat.completions.create(
                model="gpt-4o-mini", # old model -> gpt-3.5-turbo
                messages=[
                    {
                        "role": "user", 
                        "content": f"Create a recommendation for developers \
                            baseded on this generated issue: '\n\n{details}\n\n'. \
                            Format with markdown. \
                            Format each recommendation as a markdown task. \
                            Omit the title or header in your response. \
                            Remove any disclaimer or notes section. \
                            Remove any reference to selenium documentation. \
                            Max Length of Response: 170 words. \
                            Tone: Instructive"
                    },
                ]
            ).choices[0].message.content

        # return recommendation 
        return recommendation

    



