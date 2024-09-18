from ..models import *
from .alerts import *
import re, uuid






class Automater():
    """ 
    Build and execute `Automation` logic generated by a user.

    Expects: {
        'automation_id' : str,
        'object_id'     : str
    }

    Use `Automater.run_automation()` to run an `Automation`

    Returns -> None
    """


    def __init__(self, automation_id: str=None, object_id: str=None):
    
        self.automation = Automation.objects.get(id=automation_id)
        self.object_id = object_id
        self.exp_list = []
        self.act_list = []
        self.object = None
        self.use_exp = True




    def get_object(self) -> bool:
        """
        Tries to get the focus object from self.object - if found 
        will set self.object and self.use_exp

        Returns -> bool or object
        """

        if self.automation.schedule.task_type == 'scan':
            try:
                self.object = Scan.objects.get(id=self.object_id)
            except:
                return False

        elif self.automation.schedule.task_type == 'test':
            try:
                self.object = Test.objects.get(id=self.object_id)
            except:
                return False
        
        elif self.automation.schedule.task_type == 'report':
            try:
                self.object = Report.objects.get(id=self.object_id)
                self.use_exp = False
            except:
                return False

        elif self.automation.schedule.task_type == 'testcase':
            try:
                self.object = Testcase.objects.get(id=self.object_id)
                self.use_exp = True
            except:
                return False

        else:
            return False      
    



    def build_exp_list(self) -> None:
        """ 
        Loop through the automation.expressions
        and rebuilds into self.exp_list

        Returns -> None
        """
                
        # begin iteration
        for expression in self.automation.expressions:

            # set defaults
            exp = None
            data_type = None
            operator = ' == '
            joiner = ''
            data_type = 'self.object.passed'
            value = f"str({str(expression['value'])})"

            # getting data
            if self.object:
                
                # get comparison value
                if self.automation.schedule.task_type != 'testcase' and expression['data_type'] != 'test_status':
                    value = str(float(re.search(r'\d+', str(expression['value'])).group()))

                # get operator
                if '>=' in expression['operator']:
                    operator = ' >= '
                elif '<=' in expression['operator']:
                    operator = ' <= '
                else:
                    operator = ' == '
                
                # get joiner
                if 'and' in expression['joiner']:
                    joiner = ' and '
                elif 'or' in expression['joiner']:
                    joiner = ' or '
                else:
                    joiner = ''


            # high-level test data 
            if 'test_score' in expression['data_type']:
                data_type = 'float(self.object.score)'
            elif 'current_health' in expression['data_type']:
                data_type = '((float(self.object.lighthouse_delta["scores"].get("current_average",0)) + float(self.object.yellowlab_delta["scores"].get("current_average",0)))/2)'
            elif 'avg_image_score' in expression['data_type']:
                data_type = 'float(self.object.images_delta.get("average_score",0))'
            elif 'image_scores' in expression['data_type']:
                data_type = '[i["score"] for i in self.object.images_delta["images"]]' 
                exp = f'{joiner}any(i{operator}{value} for i in {data_type})'
            elif 'test_status' in expression['data_type']:
                data_type = 'self.object.status' 
            # high-level scan data
            elif 'health' in expression['data_type']:
                data_type = '((float(self.object.lighthouse["scores"].get("average",0)) + float(self.object.yellowlab["scores"].get("globalScore",0)))/2)'
            elif 'logs' in expression['data_type']:
                data_type = 'len(self.object.logs)'
            
            # LH test data
            elif 'current_lighthouse_average' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("current_average",0))'
            elif 'seo_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("seo_delta",0))'
            elif 'pwa_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("pwa_delta",0))'
            elif 'crux_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("crux_delta",0))'
            elif 'best_practices_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("best_practices_delta", 0))'
            elif 'performance_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("performance_delta",0))'
            elif 'accessibility_delta' in expression['data_type']:
                data_type = 'float(self.object.lighthouse_delta["scores"].get("accessibility_delta",0))'
            
            # LH scan data
            elif 'lighthouse_average' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("average",0))'
            elif 'seo' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("seo",0))'
            elif 'pwa' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("pwa",0))'
            elif 'crux' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("crux",0))'
            elif 'best_practices' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("best_practices",0))'
            elif 'performance' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("performance",0))'
            elif 'accessibility' in expression['data_type']:
                data_type = 'float(self.object.lighthouse["scores"].get("accessibility",0))'

            # YL test data
            elif 'current_yellowlab_average' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("current_average",0))'
            elif 'pageWeight_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("pageWeight_delta",0))'
            elif 'images_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("images_delta",0))'
            elif 'domComplexity_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("domComplexity_delta",0))'
            elif 'javascriptComplexity_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("javascriptComplexity_delta",0))'
            elif 'badJavascript_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("badJavascript_delta",0))'
            elif 'jQuery_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("jQuery_delta",0))'
            elif 'cssComplexity_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("cssComplexity_delta",0))'
            elif 'badCSS_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("badCSS_delta",0))'
            elif 'fonts_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("fonts_delta",0))'
            elif 'serverConfig_delta' in expression['data_type']:
                data_type = 'float(self.object.yellowlab_delta["scores"].get("serverConfig_delta",0))'
            
            # LH scan data
            elif 'yellowlab_average' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("globalScore",0))'
            elif 'pageWeight' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("pageWeight",0))'
            elif 'images' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("images",0))'
            elif 'domComplexity' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("domComplexity",0))'
            elif 'javascriptComplexity' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("javascriptComplexity",0))'
            elif 'badJavascript' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("badJavascript",0))'
            elif 'jQuery' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("jQuery",0))'
            elif 'cssComplexity' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("cssComplexity",0))'
            elif 'badCSS' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("badCSS",0))'
            elif 'fonts' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("fonts",0))'
            elif 'serverConfig' in expression['data_type']:
                data_type = 'float(self.object.yellowlab["scores"].get("serverConfig",0))'
            
            # building exp if not defiined
            if exp is None:
                exp = f'{joiner}{data_type}{operator}{value}'

            # adding exp to exp_list
            self.exp_list.append(exp)

        return None




    def build_act_list(self) -> None:
        """ 
        Loop through the automation.actions
        and rebuilds into self.act_list

        Returns -> None
        """

        # begin iteration
        for action in self.automation.actions:

            if 'slack' in action['action_type']:
                action_type = str(
                    f"\n  print('sending slack alert')" +
                    f"\n  automation_slack(automation_id='{str(self.automation.id)}'," +
                    f" object_id='{str(self.object_id)}')"
                )
            
            if 'webhook' in action['action_type']:
                action_type = str(
                    f"\n  print('sending webhook alert')" +
                    f"\n  automation_webhook(request_type='{action['request']}'," +
                    f" request_url='{action['url']}', request_data='{action['json']}'," +
                    f" automation_id='{str(self.automation.id)}'," +
                    f" object_id='{str(self.object_id)}')"
                )

            if 'email' in action['action_type']:
                action_type = str(
                    f"\n  print('sending email alert')" +
                    f"\n  automation_email(email='{action['email']}'," +
                    f" automation_id='{str(self.automation.id)}'," +
                    f" object_id='{str(self.object_id)}')"
                )
                if type(self.object).__name__ == 'Report':
                    action_type = str(
                        f"\n  print('sending report email')" +
                        f"\n  automation_report_email(email='{action['email']}'," +
                        f" automation_id='{str(self.automation.id)}'," +
                        f" object_id='{str(self.object_id)}')"
                    )
            
            if 'phone' in action['action_type']:
                action_type = str(
                    f"\n  print('sending phone alert')" +
                    f"\n  automation_phone(phone_number='{action['phone']}'," +
                    f" automation_id='{str(self.automation.id)}'," +
                    f" object_id='{str(self.object_id)}')"
                )

            # adding action to act_list
            self.act_list.append(action_type)




    def run_automation(self) -> None:

        # get object data
        self.get_object()

        # setting default
        exp_string = '1 == 1'

        # if obj was retrieved
        if self.object:

            # build expression if self.use_exp
            if self.use_exp:
                self.build_exp_list()
                exp_string = ' '.join(self.exp_list)

            # build action list
            self.build_act_list()
            act_string = ''.join(self.act_list)            

            # building final exec str
            automation_logic = f'if {exp_string}:{act_string}'
            print(automation_logic)

            # executing automation logic
            exec(automation_logic)

        return None


        




        


        
        