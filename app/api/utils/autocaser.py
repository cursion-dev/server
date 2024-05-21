from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from .driver_s import driver_init, driver_wait, quit_driver
from ..models import Site, Case
from scanerr import settings
import time, os, json, sys, uuid, random, boto3





class AutoCaser():


    def __init__(
            self, 
            site,
            process,
            start_url: str=None,
            configs: dict=settings.CONFIGS,
            max_cases: int=4, 
            max_layers: int=5,
        ):
         
        # main objects & configs
        self.site = site
        self.process = process
        self.start_url = start_url
        self.configs = configs
        self.max_cases = max_cases
        self.max_layers = max_layers
        
        # high-level elemets array.
        # All elememts represent the 
        # begining of a new Case.
        self.elements = []
        self.final_start_elements = []

        # starting driver
        self.driver = driver_init(
            window_size=self.configs.get('window_size'),
            device=self.configs.get('device'),
        )

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

        # setting selector script
        self.visible_script = (
            """
            const isVisible = (elm) => {
                try{
                    if (window.getComputedStyle(elm).visibility === 'hidden' || window.getComputedStyle(elm).display === 'none'){
                        return false
                    } else {
                        return true
                    }
                }catch{
                    return false
                }
            }

            return isVisible(arguments[0])
            
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
            "password":         {'test_data': 'pass123456!@', 'action': 'change'},
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
            "textarea":         {'test_data': 'This is longer example text for testing.', 'action': 'change'},
            "None":             {'test_data': None, 'action': None},
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
        



    def update_process(
            self, 
            current: int, 
            total: int, 
            complete: bool=False, 
            exception: str=None
        ) -> object:
        # calculate the current progress of the
        # task based on current iteration and total 
        # iterations expected
        final_progress = 90
        progress = 0
        success = False
        if complete:
            progress = 100
            success = True
        if not complete:
            progress = float((current/total) * final_progress)

        print(f'updating process --> {progress}%')
        
        # update Process obj
        self.process.progress = progress
        self.process.success = success
        self.process.save()




    def is_element_visible(self, element: object) -> bool: 
        try:
            resp = self.driver.execute_script(self.visible_script, element)
            resp = str(resp).lower()
            if resp == 'true':
                return True
            if resp == 'false':
                return False
        except Exception as e:
            print(f'is_element_visible() Exception -> Stale element reference')




    def get_element_image(self, element: object):
        try:
            image = element.screenshot_as_base64
            # sleep for .5 seconds to let image process
            time.sleep(.5)
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




    def get_priority_elements(self, elements: list) -> dict:
        priority_words = [
            'cart', 'checkout', 'add to cart', 'add to the cart', 
            'add to basket', 'add to shopping basket', 'add to shopping cart', 
            'add to the cart', 'billing', 'address', 'payment', 'purchase now',
            'order now', 'order', 'shop now', 'continue to payment', 'contact', 
            'apply', 'submit', 
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
                if word in elm_text.lower() or elm_text.lower() in word:
                    priority_elements.append(element)
                    break
                elif element not in non_priority_elements:
                    non_priority_elements.append(element)

        # if priotity_elements[] is empty
        # look for any forms and add them
        if len(priority_elements) == 0:
            for element in elements:
                if element.tag_name == 'form':
                    # add to priority
                    priority_elements.append(element)
                    print('added FORM to priority_elements[]')

        data = {
            'priority_elements': priority_elements, 
            'non_priority_elements': non_priority_elements
        }

        return data




    def get_current_elements(self) -> list:
        buttons = self.driver.find_elements(By.TAG_NAME, 'button')
        links = self.driver.find_elements(By.TAG_NAME, 'a')
        forms = self.driver.find_elements(By.TAG_NAME, 'form')
        inputs = self.driver.find_elements(By.TAG_NAME, 'input')
        textareas = self.driver.find_elements(By.TAG_NAME, 'textarea')
        inputs_textareas_buttons = inputs + textareas + buttons

        # get all form inputs, textareas, & buttons
        form_elems = []
        for form in forms:
            # form inputs
            form_inputs = form.find_elements(By.TAG_NAME, 'input')
            form_elems += form_inputs
            # form textarea
            form_textares = form.find_elements(By.TAG_NAME, 'textarea')
            form_elems += form_textares
            # form buttons
            form_buttons = form.find_elements(By.TAG_NAME, 'button')
            form_elems += form_buttons

        # then remove duplicates
        inputs_textareas_buttons = [elem for elem in inputs_textareas_buttons if elem not in form_elems]
        
        # shuffle elements in place
        random.shuffle(forms)
        random.shuffle(inputs_textareas_buttons)
        random.shuffle(links)
        
        current_elements = forms + inputs_textareas_buttons + links

        return current_elements




    def check_for_duplicates(self, selector: str, elements: list=None) -> bool:
        found_duplicate = False
        if elements is None:
            elements = self.elements

        # checking against all final start elements
        for final_start_elem in self.final_start_elements:
            if final_start_elem == selector:
                found_duplicate = True
                return found_duplicate

        for elem in elements:
            # check if selector exists already
            if elem['selector'] == selector:
                found_duplicate = True
                break

            # check if sub_elements exists
            if elem['elements'] != None:
                self.check_for_duplicates(selector=selector, elements=elem['elements'])
        

        # return result
        return found_duplicate




    def get_clean_elements(self, elements: list, check_against: list=None) -> list:
        cleaned_elements = []
        current_url = self.driver.current_url

        for elem in elements:
            # get slector
            elem_selector = self.driver.execute_script(self.selector_script, elem)
            
            # check local duplicates 
            if check_against is not None:
                if self.check_for_duplicates(selector=elem_selector, elements=check_against):
                    print(f'found local duplicate => {elem_selector}')
                    continue
            
            # check global duplicates
            if self.check_for_duplicates(selector=elem_selector):
                print(f'found global duplicate => {elem_selector}')
                continue
            
            # check url if <a>
            if elem.tag_name == 'a':
                # check if action will reload page or site root
                elem_link = elem.get_attribute('href')
                if current_url == elem_link or elem_link == self.site.site_url or elem_link == '/':
                    print('elem reloads page')
                    continue
                # check if action will nav to new site
                if not elem_link.startswith(self.site.site_url):
                    print(f'elem links to different site')
                    continue

            # add to cleaned conditions passed
            cleaned_elements.append(elem)
        
        # return cleaned elements
        return cleaned_elements




    def record_new_element(self, elem: object, sub_elements: list) -> dict:
        """
            returns -> {
                'sub_elements': [],
                'run': bool,
                'added': bool,
            }
        """
        # setting defaults
        run = True
        added = False

        # check if element is visible
        if not self.is_element_visible(elem):
            data = {
                'run': run,
                'added': added,
                'sub_elements': sub_elements
            }
            return data

        # get sub element info
        elem_selector = self.driver.execute_script(self.selector_script, elem)
        elem_img = self.get_element_image(element=elem)
        relative_url = self.get_relative_url(self.driver.current_url)
        
        # found new element, record, click, & continue
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
            added = True
            run = True

        
        # found new input or textarea
        elif elem.tag_name == 'input' or elem.tag_name == 'textarea':
            
            # getting element values and type
            type = str(elem.get_attribute('type'))
            value = elem.get_attribute('value')
            if elem.tag_name == 'textarea':
                type = 'textarea'

            # record element
            sub_elements.append({
                'selector': elem_selector,
                'elem_type': elem.tag_name,
                'placeholder': elem.get_attribute('placeholder'),
                'value': value,
                'type': type,
                'data': self.input_types[type]['test_data'],
                'action': self.input_types[type]['action'],
                'path': relative_url,
                'img': elem_img,
                'elements': None,
            })
            
            # add to layers and ending internal loop
            added = True
            run = True
        

        # found new form, record and end run
        elif elem.tag_name == 'form':
            
            # record form into sub_elements list
            sub_elements = self.record_forms(
                elements=sub_elements, 
                form=elem
            )

            # add to layers and ending case
            added = True
            run = False

        data = {
            'sub_elements': sub_elements,
            'run': run,
            'added': added
        }

        return data 
        



    def record_forms(self, elements: list, form: object=None) -> list:

        # wait for page to load 
        driver_wait(
            driver=self.driver,
            interval=self.configs.get('interval'),
            max_wait_time=self.configs.get('max_wait_time'),
            min_wait_time=self.configs.get('min_wait_time'),
        )

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
            
            # defining form.elements
            sub_elements = []

            # get all input fields in form
            inputs = form.find_elements(By.TAG_NAME, "input")
            # iterate through each input
            for i in inputs:
                
                if i.get_attribute('type') not in self.blacklist and self.is_element_visible(i):
                    # get input data
                    input_selector = self.driver.execute_script(self.selector_script, i)
                    placeholder = i.get_attribute('placeholder')
                    value = i.get_attribute('value')
                    type = str(i.get_attribute('type'))
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


            # get all textarea fields in form
            textareas = form.find_elements(By.TAG_NAME, "textarea")
            # iterate through each input
            for i in textareas:
                
                if i.get_attribute('type') not in self.blacklist and self.is_element_visible(i):
                    # get input data
                    input_selector = self.driver.execute_script(self.selector_script, i)
                    placeholder = i.get_attribute('placeholder')
                    type = str(i.get_attribute('type'))
                    img = self.get_element_image(element=i)
                    relative_url = self.get_relative_url(self.driver.current_url)

                    sub_elements.append({
                        'selector': input_selector,
                        'elem_type': i.tag_name,
                        'placeholder': placeholder,
                        'value': None,
                        'type': type,
                        'data': self.input_types['textarea']['test_data'],
                        'action': self.input_types['textarea']['action'],
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
                    
                    if i.get_attribute('type') not in self.blacklist and self.is_element_visible(i):
                        # get input data
                        input_selector = self.driver.execute_script(self.selector_script, i)
                        placeholder = i.get_attribute('placeholder')
                        value = i.get_attribute('value')
                        type = str(i.get_attribute('type'))
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

                if self.is_element_visible(btn):
                    # get button data
                    btn_selector = self.driver.execute_script(self.selector_script, btn)
                    type = str(btn.get_attribute('type'))
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




    def get_elements(self):

        # get site page
        if self.start_url is not None:
            self.driver.get(self.start_url)
        if self.start_url is None:
            self.driver.get(self.site.site_url)
        start_page = self.driver.current_url

        # record all forms and sub_elements on page
        self.elements = self.record_forms(elements=self.elements)
    
        # grab all buttons
        buttons = self.driver.find_elements(By.TAG_NAME, "button")

        # grab all links
        links = self.driver.find_elements(By.TAG_NAME, "a")

        # combine buttons and links
        start_elms = buttons + links

        # clean start element
        cleaned_start_elems = self.get_clean_elements(start_elms)

        # sorting start_elems
        sorted_elements = self.get_priority_elements(
            elements=cleaned_start_elems, 
        )
        priority_elements = sorted_elements['priority_elements']
        non_priority_elements = sorted_elements['non_priority_elements']

        # ending early if not enough elements to generate with
        if len(priority_elements) <= 1 and len(non_priority_elements) <= 1:
            return self.elements

        # choosing random priority element
        if len(priority_elements) > 0:
            choosen = priority_elements[
                random.randint(0, (len(priority_elements) - 1)) if len(priority_elements) > 1 else 0
            ]
            self.final_start_elements.append(
                self.driver.execute_script(self.selector_script, choosen)
            )

        # adding random elements to self.final_start_elements[]
        # until max_cases" is reached
        iterations = 0
        while (len(self.final_start_elements) + len(self.elements)) < self.max_cases and iterations < (5 * self.max_cases):

            # random choice
            choosen = non_priority_elements[
                random.randint(0, (len(non_priority_elements) - 1)) if len(non_priority_elements) > 1 else 0
            ]

            # checking if chosen element is visible
            if not self.is_element_visible(choosen):
                iterations += 1
                continue

            # check if element exists in self.final_start_elements[]
            selector = self.driver.execute_script(self.selector_script, choosen)
            if selector in self.final_start_elements:
                iterations += 1
                continue
            
            # ensuring link is local to site
            if choosen.tag_name == 'a':
                link_text = choosen.get_attribute('href')
                if link_text.startswith(self.get_url_root(start_page)):
                    self.final_start_elements.append(selector)
                    
            # adding if button
            if choosen.tag_name == 'button':
                self.final_start_elements.append(selector)

            # forcing loop to quit if not enough cases are created
            iterations += 1


        # begin elem iteration
        iterations = 0
        for selector in self.final_start_elements:

            # ensuring we're at start_page
            if self.driver.current_url != start_page:
                self.driver.get(start_page)
                driver_wait(
                    driver=self.driver,
                    interval=self.configs.get('interval'),
                    max_wait_time=self.configs.get('max_wait_time'),
                    min_wait_time=self.configs.get('min_wait_time'),
                )

            # getting element by selector
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
            except Exception as e:
                print('Element not Reachable, removing')
                self.final_start_elements.remove(selector)
                iterations += 1
                continue
            
            # get element info
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
                self.final_start_elements.remove(selector)
                continue


            # begin layering (max_layers)
            layers = 0
            run = True
            sub_elements = []
            while layers < self.max_layers and run:

                print(f'on layer -> {layers}')

                # driver wait
                driver_wait(
                    driver=self.driver,
                    interval=self.configs.get('interval'),
                    max_wait_time=self.configs.get('max_wait_time'),
                    min_wait_time=self.configs.get('min_wait_time'),
                )

                # check current page
                if self.driver.current_url == previous_url:
                    
                    # check for new element
                    new_elements = self.get_current_elements()
                    
                    # cleaning new elements
                    cleaned_elements = self.get_clean_elements(new_elements, check_against=sub_elements)

                    # iterating through each elem 
                    recorded_element = False
                    for elem in cleaned_elements:

                        # record element and increment if necessary
                        data = self.record_new_element(elem, sub_elements) 
                        run = data['run']
                        layers += 1 if data['added'] else 0
                        sub_elements = data['sub_elements']
                        recorded_element = data['added']
                        
                    # add to layers
                    if not recorded_element:
                        layers += 1


                # check if page is different but still on site
                elif self.driver.current_url != previous_url and \
                    self.driver.current_url.startswith(self.get_url_root(previous_url)):

                    # get new elements and randomly choose 1 (with priority)
                    new_elements = self.get_current_elements()

                    # cleaning new elements
                    cleaned_elements = self.get_clean_elements(new_elements, check_against=sub_elements)

                    # sort new elements
                    sorted_elements = self.get_priority_elements(
                        elements=cleaned_elements,
                    )
                    priority_elements = sorted_elements['priority_elements']
                    non_priority_elements = sorted_elements['non_priority_elements']
                    elem = None
                    
                    # choosing random priority elememt 
                    if len(priority_elements) > 0:
                        elem = priority_elements[
                            random.randint(0, (len(priority_elements) - 1)) if len(priority_elements) > 1 else 0
                        ]
                        print(f'chose priority element | type -> {elem.tag_name}')

                    # choosing a random non-priority element
                    elif len(non_priority_elements) > 0:
                        elem = non_priority_elements[
                            random.randint(0, (len(non_priority_elements) - 1)) if len(non_priority_elements) > 1 else 0
                        ]
                        print(f'chose non-priority element | type -> {elem.tag_name}')

                    # returning early if no elem selected
                    if not elem:
                        print('no element was selected')
                        # add to layers and ending case
                        layers += 1
                        run = False
                        break
            
                    # record element and increment if necessary
                    data = self.record_new_element(elem, sub_elements) 
                    run = data['run']
                    layers += 1 if data['added'] else 0
                    sub_elements = data['sub_elements']

                    # catching all other situations
                    # naving back to previous_url   
                    if not data['added']:
                        print('no coditions were met')
                        # add to layers
                        layers += 1
                        # going back
                        self.driver.get(previous_url)

                # catching all other situations
                # naving back to previous_url   
                else:
                    print('no coditions were met')
                    # add to layers
                    layers += 1
                    # going back
                    self.driver.get(previous_url)
                    
                
            # adding final info to elememt list
            self.elements.append({
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

            # counting for process 
            iterations += 1

            # update process
            self.update_process(current=iterations, total=len(self.final_start_elements))

        # quit driver session
        quit_driver(self.driver)

        # return elements
        return self.elements




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
                        if elem['action'] is not None:
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
                id       = case_id,
                site     = self.site,
                site_url = self.site.site_url,
                user     = self.site.user,
                account  = self.site.account,
                name     = element['elem_text'] if len(element['elem_text']) > 0 else f'Case {str(case_id)[0:5]}',
                type     = "generated",
                steps    = {
                    'url':  steps_url,
                    'num_steps': len(steps)
                },
            )

        # update process
        self.update_process(current=1, total=1, complete=True)


        return None




