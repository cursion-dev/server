from .driver import driver_init, driver_wait
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
import time







class Wordpress():


    def __init__(
        self, 
        login_url, 
        admin_url, 
        username, 
        password,
        wait_time, 
        ):
        self.login_url = login_url
        self.username = username
        self.password = password
        if wait_time is None:
            self.driver = driver_init()
        else:
            self.driver = driver_init(wait_time=wait_time)
        self.native_lang = 'en'

        if not admin_url.endswith('/'):
            admin_url = admin_url + '/'
        self.admin_url = admin_url




    def login(self):

        ''' 
            Tries to log into a WP site with given credentials.

            returns --> True / False 
        
        '''

        print('begining login method for ' + self.login_url)
        try:
            self.driver.get(self.login_url)
            try:
                self.driver.find_element_by_xpath('//*[@id="user_login"]')
                print('found login form')
            except:
                try:
                    self.driver.find_element_by_xpath(
                        '//*[@id="jetpack-sso-wrap"]/a[1]').click()
                    self.driver.find_element_by_xpath('//*[@id="user_login"]')
                    print('found login form')
                except:
                    try:
                        self.driver.find_element_by_link_text(
                            'Login with username and password').click()
                        self.driver.find_element_by_xpath('//*[@id="user_login"]')
                        print('found login form')
                    except:
                        print('unable to locate login form at this path')
                        self.driver.quit()
                        return False
                    
    
        except:
            print('unable to locate login form at this path')
            self.driver.quit()
            return False

        user_name_elem = self.driver.find_element_by_xpath('//*[@id="user_login"]')
        user_name_elem.clear()
        user_name_elem.send_keys(self.username)
        time.sleep(1)
        passworword_elem = self.driver.find_element_by_xpath('//*[@id="user_pass"]')
        passworword_elem.clear()
        passworword_elem.send_keys(self.password)
        time.sleep(1)
        passworword_elem.send_keys(Keys.RETURN)

        try:
            

            try:
                verify_email = self.driver.find_element_by_xpath('//*[@id="correct-admin-email"]')
                print('need to verify email')
                self.driver.execute_script('arguments[0].click();', verify_email)
                print('clicked verify')
            except:
                pass

            print('done with login attempt')

            try:
                self.driver.find_element_by_xpath('//*[@id="login_error"]')
                print('found login error')
                self.driver.refresh()

                print('trying login again')
                user_name_elem = self.driver.find_element_by_xpath('//*[@id="user_login"]')
                user_name_elem.clear()
                user_name_elem.send_keys(self.username)
                time.sleep(1)
                passworword_elem = self.driver.find_element_by_xpath('//*[@id="user_pass"]')
                passworword_elem.clear()
                passworword_elem.send_keys(self.password)
                time.sleep(1)
                passworword_elem.send_keys(Keys.RETURN)

                try:
                    self.driver.find_element_by_xpath('//*[@id="login_error"]')
                    print('found login error again')
                    print('counld not login to this site')
                except:
                    print('no login errors')

            except:
                print('no login errors')

        except:
            print('counld not login to this site')
            self.driver.quit()
            return False
            

        # removing alerts
        try:
            deny_btn = self.driver.find_element_by_id('webpushr-deny-button')
            self.driver.execute_script("arguments[0].click();", deny_btn)
            print('removed alert')
        except:
            pass

        try:
            # checking if url location is wp-admin
            current_url = str(self.driver.current_url)
            admin_link = '/wp-admin/'
            print('current url -> ' + current_url)
            if current_url.endswith("/wp-admin") or current_url.endswith("/wp-admin/") or admin_link in current_url:
                pass
            else:
                print('not in wp-admin - navigating there now')
                admin_btn = self.driver.find_element_by_id('wp-admin-bar-dashboard')
                admin_link = admin_btn.find_element_by_tag_name('a')
                self.driver.execute_script("arguments[0].click();", admin_link)
                print('clicked dashboard link')
        
        except:
            print('could not login')
            self.driver.quit()
            return False

        
        return True




    
    def begin_lang_check(self):

        try:
            # navigate to settings
            s_url = 'options-general.php'
            try:
                settings_menu = self.driver.find_element_by_xpath('//*[@id="menu-settings"]')
                self.driver.execute_script("arguments[0].click();", settings_menu)
                settings = self.driver.find_element_by_xpath('.//a[@href="'+s_url+'"]')
                self.driver.execute_script("arguments[0].click();", settings)
                print('clicked settings tab')
            except:
                current_url = self.driver.current_url
                self.driver.get(current_url + s_url)

            # finding and recording current native language
            lang_selector = self.driver.find_element_by_id('WPLANG')
            optgroup = lang_selector.find_elements_by_tag_name('optgroup')[0]
            selected_lang = optgroup.find_element_by_xpath('.//option[@selected="selected"]')
            default_lang = selected_lang.get_attribute('lang')
            default_lang_value = selected_lang.get_attribute('value')
            print("defalut lang value is " + str(default_lang))
            
            if default_lang != 'en':

                # selecting english
                select = Select(lang_selector)
                select.select_by_value('en_CA')
                print('selected english')

                # saving settings
                save_btn = self.driver.find_element_by_id('submit')
                self.driver.execute_script("arguments[0].scrollIntoView();", save_btn)
                self.driver.execute_script("arguments[0].click();", save_btn)
                print('saved lang to english')
                
                self.native_lang = default_lang_value
                return True

            else:
                self.native_lang = 'en'


        except:
            print('error in changing language')
            return False






    def end_lang_check(self):

        if self.native_lang != 'en':

            try:
                # navigate to settings
                s_url = 'options-general.php'
                try:
                    settings_menu = self.driver.find_element_by_xpath('//*[@id="menu-settings"]')
                    self.driver.execute_script("arguments[0].click();", settings_menu)
                    settings = self.driver.find_element_by_xpath('.//a[@href="'+s_url+'"]')
                    self.driver.execute_script("arguments[0].click();", settings)
                    print('clicked settings tab')
                except:
                    current_url = self.driver.current_url
                    self.driver.get(current_url + '/' + s_url)

                # selecting native lang
                lang_selector = self.driver.find_element_by_id('WPLANG')
                select = Select(lang_selector)
                select.select_by_value(self.native_lang)
                print('selected native_lang')

                # saving settings
                save_btn = self.driver.find_element_by_id('submit')
                self.driver.execute_script("arguments[0].scrollIntoView();", save_btn)
                self.driver.execute_script("arguments[0].click();", save_btn)
                print('saved native lang')

            except:
                self.driver.quit()
                return False

        self.driver.quit()
        return True



    def install_plugin(self, plugin_name):

        # setting url for link naving
        plugin_menu_page = 'plugins.php'
        add_plugin_page = 'plugin-install.php'

        # navigating to plugin page   
        try:
            print('trying click method')
            plugin_menu = self.driver.find_element_by_xpath('//*[@id="menu-plugins"]')
            self.driver.execute_script("arguments[0].click();", plugin_menu)
            p_url = 'plugins.php'
            plugins = self.driver.find_element_by_xpath('.//a[@href="'+p_url+'"]')
            self.driver.execute_script("arguments[0].click();", plugins)
            print('clicked plugin menu')
            
            # looking for dependencies in plugin table
            time.sleep(10)
            form = self.driver.find_element_by_id('bulk-action-form')
            pluginTable = form.find_element_by_tag_name('tbody')
            self.driver.execute_script("arguments[0].scrollIntoView();", pluginTable)
            print('scrolled to plugin table')
            time.sleep(1)
            tableText = pluginTable.text

        except:
            print('trying link method for navigation')
            try:
                self.driver.get(self.admin_link + plugin_menu_page)
                time.sleep(10)
                # looking for dependencies in plugin table
                time.sleep(10)
                form = self.driver.find_element_by_id('bulk-action-form')
                pluginTable = form.find_element_by_tag_name('tbody')
                self.driver.execute_script("arguments[0].scrollIntoView();", pluginTable)
                print('scrolled to plugin table')
                time.sleep(1)
                tableText = pluginTable.text
            except:
                print('unable to find plugin table')
                self.driver.quit()
                return False

        if plugin_name not in tableText:
            try:
                print('plugin not present, preparing to install')

                time.sleep(2)
                print('navigating to add plugins page')
                
                try:
                    url = 'plugin-install.php'
                    add_plugin = self.driver.find_element_by_xpath('//a[@href="'+url+'"]')
                    self.driver.execute_script("arguments[0].click();", add_plugin)
                    print('clicked add plugin link')
                    time.sleep(5)
                except:
                    self.driver.get(self.admin_url + add_plugin_page)
                    time.sleep(5)

                
                # searching for plugin
                search_form = self.driver.find_element_by_xpath('//input[@type="search"]')
                search_form.clear()
                search_form.send_keys(plugin_name)
                time.sleep(1)
                search_form.send_keys(Keys.RETURN)
                time.sleep(3)

                ##### Clicking Updraft "install" plugin ######
                install = self.driver.find_element_by_xpath('//*[@id="the-list"]/div[1]/div[1]/div[2]/ul/li[1]/a') #### ---> This will have to updated regularly 
                self.driver.execute_script("arguments[0].scrollIntoView();", install)
                time.sleep(1)
                self.driver.execute_script('arguments[0].click();', install)
                print('Clicked -install plugin-')
                time.sleep(30)
            
            
                #### Clicking "activate" plugin ######
                self.driver.refresh()
                time.sleep(3)
                activate = self.driver.find_element_by_xpath('//*[@id="the-list"]/div[1]/div[1]/div[2]/ul/li[1]/a') #### ---> This will have to updated regularly 
                self.driver.execute_script("arguments[0].scrollIntoView();", activate)
                time.sleep(1)
                self.driver.execute_script('arguments[0].click();', activate)
                print('Clicked -Activate plugin-')
                time.sleep(30)
                print('Dependencies installed sucessfully')
                return True

            except:
                print('failed dependency installation')
                self.driver.quit()
                return False