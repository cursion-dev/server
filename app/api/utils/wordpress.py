from .driver_s import driver_init, driver_wait
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from ..models import * 
from datetime import datetime
import time, uuid







class Wordpress():


    def __init__(
        self, 
        login_url, 
        admin_url, 
        username, 
        password,
        email_address,
        destination_url,
        sftp_address,
        dbname,
        sftp_username,
        sftp_password,
        wait_time, 
        process_id
        ):
        
        # set all global vars
        self.login_url = login_url
        self.username = username
        self.password = password
        self.email_address = email_address
        self.destination_url = destination_url
        self.sftp_address = sftp_address
        self.dbname = dbname
        self.sftp_username = sftp_username
        self.sftp_password = sftp_password
        self.process = Process.objects.get(id=process_id)

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

                ##### Clicking "install" plugin ######
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

        else:
            print('plugin already installed')
            return True
             


    def launch_migration(self):
        ''' 
            Launches the migration plugin once Activated.

            returns --> True / False 
        
        '''

        # setting url for link naving
        migrate_page = 'admin.php?page=cloudways'
        current_url = self.driver.current_url

        if not current_url.endswith("cloudways"):
            print('navigating to migration page')
            if self.admin_url.endswith('/'):
                self.driver.get(f'{self.admin_url}{migrate_page}')
            else:
                self.driver.get(f'{self.admin_url}/{migrate_page}')
            time.sleep(10)
        print(f'current url -> {self.driver.current_url}')
        self.driver.save_screenshot('error.png')

        # wait for cloudways email field to become visible
        # entering self.email_address in field
        # get_element_by_name="email" -> self.email_address
        email = self.driver.find_element_by_name('email')
        email.send_keys(self.email_address)
        print('entered cloudways email')

        # checking T&S checbox
        # get_element_by_name="consent".click()
        self.driver.find_element_by_name('consent').click()
        print('checked T&S agreement')

        # clicking submit to launch migration plugin
        # get_element_by_id="migratesubmit".click()
        self.driver.find_element_by_id('migratesubmit').click()
        print('clicked migrate button')

        return True

    
    def run_migration(self):
        ''' 
            Enters data on migration page, initiates miration 
            and begins updating the associated `Process` with data
            from the page.

            returns --> True / False 
        
        '''

        # check for page to fully load 
        print('waiting 10 sec for new page to load')
        time.sleep(10)
        ## enter all necessary data in each field

        # get_element_by_name="address" -> self.destination_url
        destination_url = self.driver.find_element_by_name('address')
        destination_url.send_keys(self.destination_url)
        print(f'dest_url as -> {self.destination_url}')
        time.sleep(2)

        # get_element_by_name="newurl" -> self.sftp_address 
        sftp_address = self.driver.find_element_by_name('newurl')
        sftp_address.send_keys(self.sftp_address)
        print(f'sftp_address as -> {self.sftp_address}')
        time.sleep(2)

        # get_element_by_name="appfolder" -> self.dbname
        dbname = self.driver.find_element_by_name('appfolder')
        dbname.send_keys(self.dbname)
        print(f'dbname as -> {self.dbname}')
        time.sleep(2)


        # get_element_by_name="username" -> self.sftp_username
        sftp_username = self.driver.find_element_by_name('username')
        sftp_username.send_keys(self.sftp_username)
        print(f'sftp_username as -> {self.sftp_username}')
        time.sleep(2)

        # get_element_by_name="passwd" -> self.sftp_password
        sftp_password = self.driver.find_element_by_name('passwd')
        sftp_password.screenshot('sftp_password.png')
        sftp_password.send_keys(self.sftp_password)
        print(f'sftp_password as -> {self.sftp_password}')
        time.sleep(2)

        self.driver.execute_script("document.getElementById('source-root-dir-yes').click()")
        print('clicked root-dir-yes')
        time.sleep(2)


        print('entered all creds')
        pic_id = uuid.uuid4()
        image = self.driver.save_screenshot(f'{pic_id}.png')

        # submit data
        # get_element_by_text="MIGRATE".click()
        sftp_password.send_keys(Keys.RETURN)
        print('pressed return key')

        

        # update self.process with info_url
        self.process.info_url = self.driver.current_url
        self.process.save()

        done = False
        done_text = 'Your migration is complete!'
        new_progress = 0
        print(f'current url -> {self.driver.current_url}')
        while not done:

            # get_element_by_name="the main progress bar"
            # full xpath -> html/body/div/span/div[2]/span/div/div/div/div/div/div[3]/div[4]/div[2]
            #  //*[@id="app"]/span/div[2]/span/div/div/div/div/div/div[3]/div[4]/div[2]
            # element -> <div class="progress-percentage font16">60%</div>
            
            try:
                new_progress = self.driver.find_element_by_xpath('//*[@id="app"]/span/div[2]/span/div/div/div/div/div/div[3]/div[4]/div[2]').text()
                print(f'raw text => {new_progress}')
                new_progress = float(new_progress.split('%')[0])
                print(f'current progress -> {new_progress} %')
            except:
                try:
                    print('second method to get progress')
                    new_progress = self.driver.find_elements_by_class_name('progress-percentage font16')[2].text()
                    print(f'raw text => {new_progress}')
                    new_progress = float(new_progress.split('%')[0])
                    print(f'current progress -> {new_progress} %')

                except:
                    print('can\'t find main progress bar')
            

            # update self.process
            self.process.progress = new_progress

            # check if new_progress is 100%
            # <h1 class="font-36 color-0E134F proxima-regular mt-1 mb-2">Your migration is complete!</h1>
            # get full page div 
            if new_progress >= 100 or done_text in self.driver.page_source:
                self.process.success = True
                self.process.time_completed = datetime.now()
                done = True

            # checking for process errors
            try:
                self.driver.find_elements_by_class_name('alert alert-danger')
                done = True
                self.process.time_completed = datetime.now()
                print('found an error - ending process')
                self.process.save()
                return False
            except:
                pass

            # saving new data
            self.process.save()

            time.sleep(1)


        return True
        


            
            








        



