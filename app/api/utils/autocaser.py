from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from .driver_s import driver_init, driver_wait, quit_driver
from ..models import Site, Case
from scanerr import settings
import time, os, json, sys, uuid, random, boto3





class AutoCaser():


    def __init__(self, site, max_cases: int=4, max_layers: int=5):
         
        # main site object & configs
        self.site = site
        self.max_cases = max_cases
        self.max_layers = max_layers

        # starting driver
        self.driver = driver_init()

        # setting selector script
        self.selector_script = (
            """
            const getSelector = (elm) => {
                if (elm.tagName === "BODY") return "BODY";
                const names = [];
                while (elm.parentElement && elm.tagName !== "BODY") {
                    if (elm.id) {
                        names.unshift(`[id='${elm.getAttribute("id")}']`); // "#" + elm.getAttribute("id")
                        break;
                    } else {
                        let c = 1, e = elm;
                        for (; e.previousElementSibling; e = e.previousElementSibling, c++) ;
                        names.unshift(elm.tagName + ":nth-child(" + c + ")");
                    }
                    elm = elm.parentElement;
                }
                return names.join(">");
            }

            return getSelector(arguments[0])
            
            """
        )

        # setting defaults for inputs
        self.input_types = {
            "button":           {'test_data': None, 'action': 'click'},
            "checkbox":         {'test_data': None, 'action': 'click'},
            "color":            {'test_data': '#ff0000', 'action': 'change'},
            "date":             {'test_data': '2024-04-23', 'action': 'change'},
            "datetime-local":   {'test_data': '2024-04-22T12:49', 'action': 'change'},
            "email":            {'test_data': 'jane@example.com', 'action': 'change'},
            "file":             {'test_data': None, 'action': None},
            "hidden":           {'test_data': None, 'action': None},
            "image":            {'test_data': None, 'action': None},
            "month":            {'test_data': '2024-04', 'action': 'change'},
            "number":           {'test_data': '1', 'action': 'change'},
            "password":         {'test_data': 'pass123456!@', 'action': 'click'},
            "radio":            {'test_data': None, 'action': 'click'},
            "range":            {'test_data': 1, 'action': 'change'},
            "reset":            {'test_data': None, 'action': None},
            "search":           {'test_data': 'search example', 'action': 'change'},
            "submit":           {'test_data': None, 'action': 'click'},
            "tel":              {'test_data': '5555555555', 'action': 'change'},
            "text":             {'test_data': 'Example Text', 'action': 'change'},
            "time":             {'test_data': '12:34', 'action': 'change'},
            "url":              {'test_data': 'https://example.com', 'action': 'change'},
            "week":             {'test_data': '2024-W15', 'action': 'change'},
        }

        # setting blacklist for input types to ignore
        self.blacklist = ['file', 'hidden', 'image', 'reset']

        # setup boto3 configurations
        self.s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME), 
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )
        







    def get_element_image(self, element: object):
        try:
            image = element.screenshot_as_base64
        except:
            image = None
        return image




    def get_url_root(self, url: str) -> str:
        protocol = url.split('//')[0] + '//'
        root_url = protocol + url.split('//')[1].split('/')[0]
        return root_url




    def get_relative_url(self, url: str) -> str:
        relative_url = '/' + url.split('//')[1].split('/')[1]
        return relative_url




    def get_elem_text(self, selector: str) -> str:
        elem_text = self.driver.execute_script(f'return document.querySelector("{selector}").innerText') 
        elem_text = elem_text.split('\n')[0].strip()
        return elem_text




    def record_forms(self, elements: list, form: object=None) -> list:

        # wait for page to load 
        driver_wait(driver=self.driver)

        # building forms list
        if form is None:
            # get all forms on the page
            forms = self.driver.find_elements(By.TAG_NAME, "form")
        else:
            # adding single form to que
            forms = [form]
        
        # begin iteration of <form> gathering
        for form in forms:
            
            # get form selector
            form_selector = self.driver.execute_script(self.selector_script, form)

            print(f'recording form -> {form_selector}')

            # getting form text
            elem_text = self.get_elem_text(selector=form_selector)

            # get form image
            form_img = self.get_element_image(element=form)
            
            # get all input fields in form
            inputs = form.find_elements(By.TAG_NAME, "input")

            # iterate through each input
            sub_elements = []
            for i in inputs:
                
                if i.get_attribute('type') not in self.blacklist:
                    # get input data
                    input_selector = self.driver.execute_script(self.selector_script, i)
                    placeholder = i.get_attribute('placeholder')
                    value = i.get_attribute('value')
                    type = i.get_attribute('type')
                    img = self.get_element_image(element=i)
                    relative_url = self.get_relative_url(self.driver.current_url)

                    sub_elements.append({
                        'selector': input_selector,
                        'elem_type': i.tag_name,
                        'placeholder': placeholder,
                        'value': value,
                        'type': type,
                        'data': self.input_types[type]['test_data'],
                        'action': self.input_types[type]['action'],
                        'path': relative_url,
                        'img': img,
                        'elements': None,
                    })

            # get all iframes elements in form
            iframes = form.find_elements(By.TAG_NAME, "iframe")

            # iterate through iframes and save data
            for iframe in iframes:
                
                # get iframe data
                iframe_selector = self.driver.execute_script(self.selector_script, iframe)
                iframe_img = self.get_element_image(element=iframe)
                relative_url = self.get_relative_url(self.driver.current_url)
                
                # get all inputs for iframe
                iframe_inputs = iframe.find_elements(By.TAG_NAME, "input")

                # iterate through each input
                iframe_elements = []
                for i in iframe_inputs:
                    
                    if i.get_attribute('type') not in self.blacklist:
                        # get input data
                        input_selector = self.driver.execute_script(self.selector_script, i)
                        placeholder = i.get_attribute('placeholder')
                        value = i.get_attribute('value')
                        type = i.get_attribute('type')
                        img = self.get_element_image(element=i)
                        relative_url = self.get_relative_url(self.driver.current_url)

                        # save internal iframe data
                        iframe_elements.append({
                            'selector': input_selector,
                            'elem_type': i.tag_name,
                            'placeholder': placeholder,
                            'value': value,
                            'type': type,
                            'data': self.input_types[type]['test_data'],
                            'action': self.input_types[type]['action'],
                            'path': relative_url,
                            'img': img,
                            'elements': None,
                        })
                
                # save sub elem data
                sub_elements.append({
                    'selector': iframe_selector,
                    'elem_type': iframe.tag_name,
                    'placeholder': None,
                    'value': None,
                    'type': None,
                    'data': None,
                    'action': 'switch_to_frame',
                    'path': relative_url,
                    'img': iframe_img,
                    'elements': iframe_elements,
                })



            # get all button elements in form
            btns = form.find_elements(By.TAG_NAME, "button")

            # iterate through each btn
            for btn in btns:

                # get button data
                btn_selector = self.driver.execute_script(self.selector_script, btn)
                type = btn.get_attribute('type')
                btn_img = self.get_element_image(element=btn)
                relative_url = self.get_relative_url(self.driver.current_url)

                sub_elements.append({
                    'selector': btn_selector,
                    'elem_type': 'button',
                    'placeholder': None,
                    'value': None,
                    'type': type,
                    'data': None,
                    'elements': None,
                    'action': 'click',
                    'path': relative_url,
                    'img': btn_img,
                    'elements': None,
                })


            # save elem data
            elements.append({
                'selector': form_selector,
                'elem_type': 'form',
                'elem_text': elem_text,
                'value': None,
                'type': None,
                'data': None,
                'action': None,
                'path': relative_url,
                'img': form_img,
                'elements': sub_elements,

            })
        
        # return elements array 
        return elements




    def get_priority_elements(self, elements: list) -> dict:
        priority_words = [
            'cart', 'checkout', 'add to cart', 'add to the cart', 
            'add to basket', 'add to shopping basket', 'add to shopping cart', 
            'add to the cart', 'billing', 'address', 'payment', 'purchase now',
            'order now', 'order', 'shop now', 'continue to payment',
        ]

        priority_elements = []
        non_priority_elements = []

        # checking each element for prioriry words
        for element in elements:

            # get element's innerText
            elem_selector = self.driver.execute_script(self.selector_script, element)
            elm_text = self.driver.execute_script(f'return document.querySelector("{elem_selector}").innerText')

            # check each priority word against element innerText
            for word in priority_words:
                if word in elm_text.lower():
                    priority_elements.append(element)
                    break
                elif element not in non_priority_elements:
                    non_priority_elements.append(element)

        data = {
            'priority_elements': priority_elements, 
            'non_priority_elements': non_priority_elements
        }

        return data




    def get_current_elements(self) -> list:
        buttons = self.driver.find_elements(By.TAG_NAME, 'button')
        links = self.driver.find_elements(By.TAG_NAME, 'a')
        forms = self.driver.find_elements(By.TAG_NAME, 'form')
        current_elements = buttons + links + forms
        return current_elements




    def get_elements(self):

        # high-level elemets array.
        # All elememts represent the 
        # begining of a new Case.
        elements = []

        # get site page
        self.driver.get(self.site.site_url)
        start_page = self.driver.current_url

        # record all forms and sub_elements on page
        elements = self.record_forms(elements=elements)
    
        # grab all buttons
        buttons = self.driver.find_elements(By.TAG_NAME, "button")

        # grab all links
        links = self.driver.find_elements(By.TAG_NAME, "a")

        # combine buttons and links
        start_elms = buttons + links

        # sorting start_elems
        sorted_elements = self.get_priority_elements(
            elements=start_elms, 
        )
        priority_elements = sorted_elements['priority_elements']
        non_priority_elements = sorted_elements['non_priority_elements']

        final_start_elements = []

        # choosing random priority element
        if len(priority_elements) > 0:
            choosen = priority_elements[
                random.randint(0, (len(priority_elements) - 1))
            ]
            final_start_elements.append(
                self.driver.execute_script(self.selector_script, choosen)
            )

        # adding random elements until 
        # "max_cases" is reached
        iterations = 0
        while len(final_start_elements) < self.max_cases and iterations < (5 * self.max_cases):

            # random choice
            choosen = non_priority_elements[
                random.randint(0, (len(non_priority_elements) - 1))
            ]

            # check if element exists in final_start_elements[]
            selector = self.driver.execute_script(self.selector_script, choosen)
            if selector in final_start_elements:
                iterations += 1
                continue
            
            # ensuring link is local to site
            if choosen.tag_name == 'a':
                link_text = choosen.get_attribute('href')
                if link_text.startswith(self.get_url_root(start_page)):
                    final_start_elements.append(selector)
                    
            # adding if button
            if choosen.tag_name == 'button':
                final_start_elements.append(selector)

            # forcing loop to quit if not enough cases are created
            iterations += 1


        # begin elem iteration
        for selector in final_start_elements:

            # ensuring we're at start_page
            if self.driver.current_url != start_page:
                self.driver.get(start_page)
                driver_wait(driver=self.driver)

            # get element info
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element_img = self.get_element_image(element=element)
            element_type = element.tag_name
            elem_relative_url = self.get_relative_url(self.driver.current_url)
            elem_text = self.get_elem_text(selector=selector)

            print(f'working on this start element -> {selector}')

            # get all current elements and url before action
            old_elements = self.get_current_elements()
            previous_url = self.driver.current_url

            # perform first action
            try:
                element.click()
            except Exception as e:
                print('Element not Clickable, removing')
                final_start_elements.remove(selector)
                continue


            # begin layering (max_layers)
            layers = 0
            run = True
            sub_elements = []
            while layers < self.max_layers and run:

                print(f'layers -> {layers} | run -> {run}')

                # driver wait
                driver_wait(driver=self.driver)

                # check current page
                if self.driver.current_url == previous_url:
                    
                    # check for new element
                    new_elements = self.get_current_elements()
                    for elem in new_elements:
                        if elem not in old_elements:

                            # get sub element info
                            elem_selector = self.driver.execute_script(self.selector_script, elem)
                            elem_img = self.get_element_image(element=elem)
                            relative_url = self.get_relative_url(self.driver.current_url)
                            
                            # found new element, decide on action
                            if elem.tag_name == 'a' or elem.tag_name == 'button':

                                # record element
                                sub_elements.append({
                                    'selector': elem_selector,
                                    'elem_type': elem.tag_name,
                                    'placeholder': None,
                                    'value': None,
                                    'type': None,
                                    'data': None,
                                    'action': 'click',
                                    'path': relative_url,
                                    'img': elem_img,
                                    'elements': None,
                                })

                                # click element
                                try:
                                    elem.click()
                                except Exception as e:
                                    print('Element not Clickable, removing')
                                    sub_elements.pop()

                                # add to layers and ending internal loop
                                layers += 1
                                break

                            if elem.tag_name == 'form':
                                
                                # record form into sub_elements list
                                sub_elements = self.record_forms(
                                    elements=sub_elements, 
                                    form=elem
                                )

                                # add to layers and ending case
                                layers += 1
                                run = False
                                break
                    
                    # add to layers
                    layers += 1


                # check if page is different but still on site
                elif self.driver.current_url != previous_url and \
                    self.driver.current_url.startswith(self.get_url_root(previous_url)):

                    # get new elements and randomly choose 1 (with priority)
                    new_elements = self.get_current_elements()

                    # sort new elements
                    sorted_elements = self.get_priority_elements(
                        elements=new_elements,
                    )
                    priority_elements = sorted_elements['priority_elements']
                    non_priority_elements = sorted_elements['non_priority_elements']
                    elem = None
                    
                    # choosing random priority elememt 
                    if len(priority_elements) > 0:
                        elem = priority_elements[
                            random.randint(0, (len(priority_elements) - 1))
                        ]

                    # choosing a random non-priority element
                    elif len(non_priority_elements) > 0:
                        elem = non_priority_elements[
                            random.randint(0, (len(non_priority_elements) - 1))
                        ]

                    # returning early if no elem selected
                    if not elem:
                        # add to layers and ending case
                        layers += 1
                        run = False
                        break

                    # get sub element info
                    elem_selector = self.driver.execute_script(self.selector_script, elem)
                    elem_img = self.get_element_image(element=elem)
                    relative_url = self.get_relative_url(self.driver.current_url)

                    # check the type of element
                    if elem.tag_name == 'form':
                        # record form into sub_elements list
                        sub_elements = self.record_forms(
                            elements=sub_elements,
                            form=elem
                        )

                        # add to layers and ending case
                        layers += 1
                        run = False
                
                    if elem.tag_name == 'a' or elem.tag_name == 'button':
                        # record element
                        sub_elements.append({
                            'selector': elem_selector,
                            'elem_type': elem.tag_name,
                            'placeholder': None,
                            'value': None,
                            'type': None,
                            'data': None,
                            'action': 'click',
                            'path': relative_url,
                            'img': elem_img,
                            'elements': None,
                        })

                        # add to layers
                        layers += 1

                        # click element
                        try:
                            elem.click()
                        except Exception as e:
                            print('Element not Clickable, removing')
                            sub_elements.pop()


                # catching all other situations
                # naving back to previous_url   
                else:
                    print('no coditions were met')

                    # add to layers
                    layers += 1

                    # going back
                    self.driver.get(previous_url)
                    
                
            # adding final info to elememt list
            elements.append({
                'selector': selector,
                'elem_type': element_type,
                'elem_text': elem_text,
                'placeholder': None,
                'value': None,
                'type': None,
                'data': None,
                'action': 'click',
                'path': elem_relative_url,
                'img': element_img,
                'elements': sub_elements,
            })

        
        # quit driver session
        quit_driver(self.driver)

        # return elements
        return elements




    def build_cases(self):

        # run get_elements
        elements = self.get_elements()

        # get/decide on value for element
        def get_elem_value(element):
            if element['value'] == None or len(element['value']) <= 0:
                return element['data']
            else:
                return element['value']

        # for each high-level element, 
        # build a new `Case` and save "steps" 
        # as .json file uploaded to S3 
        for element in elements:

            # defining "steps"
            steps = []

            # adding firt step, which is naving 
            # to the the starting element's 'path'
            steps.append({
                "action":{
                    "key": "",
                    "path": element['path'],
                    "type": "navigate",
                    "value": "",
                    "element": ""
                },
                "assertion":{
                    "type": "",
                    "value": "",
                    "element": ""
                }
            })

            # adding second step if starting 
            # element is not a form
            if element['elem_type'] != 'form':
                steps.append({
                    "action":{
                        "key": "",
                        "path": element['path'],
                        "type": element['action'],
                        "value": get_elem_value(element),
                        "element": element['selector'],
                        "img": element['img']
                    },
                    "assertion":{
                        "type": "",
                        "value": "",
                        "element": ""
                    }
                })

            
            # sub_element mapping using recursion
            def sub_element_mapping(elements, steps):
                if element['elements'] != None:
                    for elem in elements:
                        # add step
                        steps.append({
                            "action":{
                                "key": "",
                                "path": elem['path'],
                                "type": elem['action'],
                                "value": get_elem_value(elem),
                                "element": elem['selector'],
                                "img": elem['img']
                            },
                            "assertion":{
                                "type": "",
                                "value": "",
                                "element": ""
                            }
                        })

                        # check if sub_elements exists
                        if elem['elements'] != None:
                            sub_element_mapping(elem['elements'], steps)

                # return mapped sub_elements in steps
                return steps

            
            # add sub_elements to steps
            steps = sub_element_mapping(element['elements'], steps)

            # create .json file for steps and upload to s3
            case_id = uuid.uuid4()

            # saving as json file temporarily
            with open(f'{case_id}.json', 'w') as fp:
                json.dump(steps, fp)
            
            # seting up paths
            steps_file = os.path.join(settings.BASE_DIR, f'{case_id}.json')
            remote_path = f'static/cases/{case_id}.json'
            root_path = settings.AWS_S3_URL_PATH
            steps_url = f'{root_path}/{remote_path}'
        
            # upload to s3
            with open(steps_file, 'rb') as data:
                self.s3.upload_fileobj(data, str(settings.AWS_STORAGE_BUCKET_NAME), 
                    remote_path, ExtraArgs={'ACL': 'public-read', 'ContentType': "application/json"}
                )

            # remove local copy
            os.remove(steps_file)

            # save new Case
            Case.objects.create(
                id      = case_id,
                site    = self.site,
                user    = self.site.user,
                account = self.site.user.account,
                name    = element['elem_text'] if len(element['elem_text']) > 0 else f'Case {str(case_id)[0:5]}',
                tags    = ["generated"],
                steps   = {
                    'url':  steps_url,
                    'num_steps': len(steps)
                },
            )


        return None




