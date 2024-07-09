from ..models import *
from scanerr import settings
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
                f'Testcase `{self.testcase.case_name}` failed on **Step {step_index}**,' + 
                f' "{failed_step['action']['type']}".\n\n'
            )
            
            # build main_issue
            main_issue = str(
                f'### Main Issue or Exception:\n' + 
                f' ```{failed_step['action']['exception']}``` \n\n' +
                f' <img src="{failed_step['action']['image']}" className="max-w-3/4"/> \n\n'
            )

            # build recommendation
            recommendation = str(
                f''
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
            comp_str = str('| Component | Score |\n|-----|-----|')
            for score in ordered_scores:
                for key in score:
                    comp_str += f'\n| {key} | {round(score[key], 2)} |'

            # build title
            title = f'Test Failed at {round(self.test.score, 2)}%'

            # build intro
            intro = str(
                f'Test failed for the page "{self.test.page.page_url}" ' + 
                f'based on the set threshold of {round(self.test.threshold, 2)}%.\n\n'
            )

            # build main_issue
            main_issue = str(
                f'### Failing Components:\n' + 
                f'{comp_str}'
            )

            # build recommendation
            recommendation = str(
                f''
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




