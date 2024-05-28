from .driver_p import driver_init
import time, asyncio, uuid
from ..models import * 
from datetime import datetime
from asgiref.sync import sync_to_async






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
        self.native_lang = 'en'

        if not admin_url.endswith('/'):
            admin_url = admin_url + '/'
        self.admin_url = admin_url

        if wait_time is None:
            self.wait_time = 30
        else:
            self.wait_time = wait_time

        self.navWaitOpt = {
            'timeout': self.wait_time * 1000,
            'waitUntil': 'domcontentloaded'
        }


    async def login(self):

        ''' 
            Tries to log into a WP site with given credentials.

            returns --> True / False 
        
        '''

        print('begining login method for ' + self.login_url)

        
        self.driver = await driver_init(wait_time=self.wait_time)

        # init page obj 
        self.page = await self.driver.newPage()
        page_options = {
            'waitUntil': 'networkidle0', 
            'timeout': self.wait_time * 1000
        }

        try:
            await self.page.goto(self.login_url, page_options)
            try:
                await self.page.xpath('//*[@id="user_login"]')
                print('found login form')
            except:
                try:
                    jetpack = await self.page.xpath('//*[@id="jetpack-sso-wrap"]/a[1]')
                    await jetpack[0].click()
                    await self.page.xpath('//*[@id="user_login"]')
                    print('found login form')
                except:
                    try:
                        login_link = await self.page.xpath("//a[contains(., 'Login with username and password')]")
                        await login_link[0].click()
                        await self.page.xpath('//*[@id="user_login"]')
                        print('found login form')
                    except:
                        print('unable to locate login form at this path')
                        await self.driver.close()
                        return False
                    
    
        except:
            print('unable to locate login form at this path')
            await self.driver.close()
            return False

        user_name_elem = await self.page.xpath('//*[@id="user_login"]')
        await user_name_elem[0].click(clickCount=3)
        await self.page.keyboard.type(self.username)
        time.sleep(1)
        passworword_elem = await self.page.xpath('//*[@id="user_pass"]')
        await passworword_elem[0].click(clickCount=3)
        await self.page.keyboard.type(self.password)
        time.sleep(1)
        await self.page.keyboard.press('Enter')
        await self.page.waitForNavigation(self.navWaitOpt)
        

        try:
            try:
                verify_email = await self.page.xpath('//*[@id="correct-admin-email"]')
                print('need to verify email')
                await verify_email[0].click()
                print('clicked verify')
            except:
                pass

            print('done with login attempt')

            try:
                await self.page.xpath('//*[@id="login_error"]')
                print('found login error')
                await self.page.reload()

                print('trying login again')
                user_name_elem = await self.page.xpath('//*[@id="user_login"]')
                await user_name_elem[0].click(clickCount=3)
                await self.page.keyboard.type(self.username)
                time.sleep(1)
                passworword_elem = await self.page.xpath('//*[@id="user_pass"]')
                await passworword_elem[0].click(clickCount=3)
                await self.page.keyboard.type(self.password)
                time.sleep(1)
                await self.page.keyboard.press('Enter')
                await self.page.waitForNavigation(self.navWaitOpt)
                

                try:
                    await self.page.xpath('//*[@id="login_error"]')
                    print('found login error again')
                    print('counld not login to this site')
                except:
                    print('no login errors')

            except:
                print('no login errors')

        except:
            print('counld not login to this site')
            
            await self.driver.close()
            return False
            

        # removing alerts
        try:
            deny_btn = await self.page.xpath('//*[@id="webpushr-deny-button"]')
            await deny_btn[0].click()
            print('removed alert')
        except:
            pass
        try:
            # checking if url location is wp-admin
            admin_link = '/wp-admin/'
            current_url = self.page.url
            print('current url -> ' + current_url)
            if current_url.endswith("/wp-admin") or current_url.endswith("/wp-admin/") or admin_link in current_url:
                print('inside wp-admin')
            else:
                print('not in wp-admin - navigating there now')
                admin_btn = await self.page.xpath('//*[@id="wp-admin-bar-dashboard"]')
                admin_link = await admin_btn[0].querySelector('a')
                await admin_link[0].click(clickCount=2)
                print('clicked dashboard link')
                await self.page.waitForNavigation(self.navWaitOpt)
                
        
        except:
            print('could not login')
            await self.driver.close()
            return False

        
        return True




    
    async def begin_lang_check(self):

        try:
            # navigate to settings
            s_url = 'options-general.php'
            try:
                settings_menu = await self.page.xpath('//*[@id="menu-settings"]')
                await settings_menu[0].click()
                print('clicked settings menu')
                await self.page.waitForNavigation(self.navWaitOpt)
                settings = await self.page.xpath('.//a[@href="'+s_url+'"]')
                await settings[0].click()
                print('clicked settings tab')
                await self.page.waitForNavigation(self.navWaitOpt)
                

            except:
                await self.page.goto(self.page.url + s_url)
                await self.page.waitForNavigation(self.navWaitOpt)

            # finding and recording current native language
            lang_selector = await self.page.xpath('//*[@id="WPLANG"]')
            optgroup = await lang_selector[0].querySelector('optgroup')
            selected_lang = await optgroup.xpath('.//option[@selected="selected"]')
            default_lang = await (await selected_lang[0].getProperty('lang')).jsonValue()
            default_lang_value = await (await selected_lang[0].getProperty('value')).jsonValue()
            print("defalut lang value is " + str(default_lang))
            
            if default_lang != 'en':

                # selecting english
                await lang_selector[0].select('en_CA')
                print('selected english')

                # saving settings
                save_btn = await self.page.xpath('//*[@id="submit"]')
                await save_btn[0].click()
                print('saved lang to english')
                
                self.native_lang = default_lang_value
                return True

            else:
                self.native_lang = 'en'


        except:
            print('error in changing language')
            return False






    async def end_lang_check(self):

        if self.native_lang != 'en':

            try:
                # navigate to settings
                s_url = 'options-general.php'
                try:
                    settings_menu = await self.page.xpath('//*[@id="menu-settings"]')
                    await settings_menu[0].click()
                    print('clicked settings menu')
                    await self.page.waitForNavigation(self.navWaitOpt)
                    settings = await self.page.xpath('.//a[@href="'+s_url+'"]')
                    await settings[0].click()
                    print('clicked settings tab')
                    await self.page.waitForNavigation(self.navWaitOpt)

                except:
                    await self.page.goto(self.page.url + s_url)
                    await self.page.waitForNavigation(self.navWaitOpt)

                # selecting native lang
                lang_selector = await self.page.xpath('//*[@id="WPLANG"]')
                await lang_selector[0].select(self.native_lang)
                print('selected native_lang')

                # saving settings
                save_btn = await self.page.xpath('//*[@id="submit"]')
                await save_btn[0].click()
                print('saved native lang')

            except:
                await self.driver.close()
                return False

        await self.driver.close()
        return True



    async def install_plugin(self, plugin_name):

        # setting url for link naving
        plugin_menu_page = 'plugins.php'
        add_plugin_page = 'plugin-install.php'

        # navigating to plugin page   
        try:
            print('trying click method')
            plugin_menu = await self.page.xpath('//*[@id="menu-plugins"]')
            await plugin_menu[0].click()
            await self.page.waitForNavigation(self.navWaitOpt)
            p_url = 'plugins.php'
            plugins = await self.page.xpath('.//a[@href="'+p_url+'"]')
            await plugins[0].click()
            print('clicked plugin menu')
            await self.page.waitForNavigation(self.navWaitOpt)
            
            
            # looking for dependencies in plugin table
            time.sleep(10)
            form = await self.page.xpath('//*[@id="bulk-action-form"]')
            pluginTable = await form[0].querySelector('tbody')
            tableText = await (await pluginTable.getProperty('textContent')).jsonValue()

        except:
            print('trying link method for navigation')
            try:
                await self.page.goto(self.admin_link + plugin_menu_page)
                await self.page.waitForNavigation(self.navWaitOpt)
                
                time.sleep(10)
                # looking for dependencies in plugin table
                form = await self.page.xpath('//*[@id="bulk-action-form"]')
                pluginTable = await form[0].querySelector('tbody')
                tableText = await (await pluginTable.getProperty('textContent')).jsonValue()
            except:
                print('unable to find plugin table')
                await self.driver.close()
                return False

        if plugin_name not in tableText:
            try:
                print('plugin not present, preparing to install')

                time.sleep(2)
                print('navigating to add plugins page')
                
                try:
                    url = 'plugin-install.php'
                    add_plugin = await self.page.xpath('//a[@href="'+url+'"]')
                    await add_plugin[0].click(clickCount=2)
                    print('clicked add plugin link')
                    await self.page.waitForNavigation(self.navWaitOpt)
                    
                    time.sleep(5)
                except:
                    await self.page.goto(self.admin_url + add_plugin_page)
                    await self.page.waitForNavigation(self.navWaitOpt)
                    
                    time.sleep(5)

                
                # searching for plugin
                search_form = await self.page.xpath('//input[@type="search"]')
                await search_form[0].click(clickCount=3)
                await self.page.keyboard.type(plugin_name)
                time.sleep(1)
                await self.page.keyboard.press('Enter')
                time.sleep(3)

                ##### Clicking "install" plugin ######
                install = await self.page.xpath('//*[@id="the-list"]/div[1]/div[1]/div[2]/ul/li[1]/a') #### ---> This will have to updated regularly 
                await install[0].click(clickCount=2)
                print('clicked -install plugin-')
                time.sleep(30)
            
            
                #### Clicking "activate" plugin ######
                await self.page.reload()
                print('reloading page')
                try:
                    await self.page.waitForNavigation(self.navWaitOpt)
                except:
                    pass
                activate = await self.page.xpath('//*[@id="the-list"]/div[1]/div[1]/div[2]/ul/li[1]/a') #### ---> This will have to updated regularly 
                await activate[0].click(clickCount=2)
                print('clicked -Activate plugin-')
                time.sleep(30)
                print('Dependencies installed sucessfully')
                return True

            except:
                print('failed dependency installation')
                await self.driver.close()
                return False

        else:
            print('plugin already installed')
            return True


    @sync_to_async
    def update_process(self, successful=False, info_url=None, time_completed=None, progress=None):
        if info_url is not None:
            self.process.info_url = info_url
        self.process.success = successful
        if time_completed is not None:
            self.process.time_completed = time_completed
        if progress is not None:
            self.process.progress = progress
        
        self.process.save()
        return



    async def launch_migration(self):
        ''' 
            Launches the migration plugin once Activated.

            returns --> True / False 
        
        '''

        # setting url for link naving
        migrate_page = 'admin.php?page=cloudways'
        current_url = self.page.url

        if not current_url.endswith("cloudways"):
            print('navigating to migration page')
            if self.admin_url.endswith('/'):
                await self.page.goto(f'{self.admin_url}{migrate_page}')
            else:
                await self.page.goto(f'{self.admin_url}/{migrate_page}')
            time.sleep(10)


        # wait for cloudways email field to become visible
        # entering self.email_address in field
        email = await self.page.xpath('//*[@id="wpbody-content"]/main/div/form/div/input')
        await email[0].click(clickCount=3)
        await self.page.keyboard.type(self.email_address)
        print('entered cloudways email')

        # checking T&S checbox
        checkbox = await self.page.xpath('//*[@id="wpbody-content"]/main/div/form/div/div/label/input[3]')
        await checkbox[0].click(clickCount=1)
        print('checked T&S agreement')

        # clicking submit to launch migration plugin
        m_button = await self.page.xpath('//*[@id="migratesubmit"]')
        await m_button[0].click(clickCount=1)
        print('clicked migrate button')

        return True

    
    async def run_migration(self):
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
        await self.page.waitForNavigation(self.navWaitOpt)

        # get_element_by_name="address" -> self.destination_url
        destination_url = await self.page.xpath('//*[@id="app"]/span/div[2]/div/div/div/div/div/form/div/div[1]/div/div/input[1]')
        await destination_url[0].click(clickCount=3)
        await self.page.keyboard.type(self.destination_url)
        print(f'dest_url as -> {self.destination_url}')
        time.sleep(2)

        # get_element_by_name="newurl" -> self.sftp_address 
        sftp_address = await self.page.xpath('//*[@id="app"]/span/div[2]/div/div/div/div/div/form/div/div[2]/div/div/input[1]')
        await sftp_address[0].click(clickCount=3)
        await self.page.keyboard.type(self.sftp_address)
        print(f'sftp_address as -> {self.sftp_address}')
        time.sleep(2)

        # get_element_by_name="appfolder" -> self.dbname
        dbname = await self.page.xpath('//*[@id="app"]/span/div[2]/div/div/div/div/div/form/div/div[3]/div/div/input[1]')
        await dbname[0].click(clickCount=3)
        await self.page.keyboard.type(self.dbname)
        print(f'dbname as -> {self.dbname}')
        time.sleep(2)

        # get_element_by_name="username" -> self.sftp_username
        sftp_username = await self.page.xpath('//*[@id="app"]/span/div[2]/div/div/div/div/div/form/div/div[4]/div/div/input[1]')
        await sftp_username[0].click(clickCount=3)
        await self.page.keyboard.type(self.sftp_username)
        print(f'sftp_username as -> {self.sftp_username}')
        time.sleep(2)

        # get_element_by_name="passwd" -> self.sftp_password
        sftp_password = await self.page.xpath('//*[@id="app"]/span/div[2]/div/div/div/div/div/form/div/div[5]/div/div/input[1]')
        await sftp_password[0].click(clickCount=3)
        await self.page.keyboard.type(self.sftp_password)
        print(f'sftp_password as -> {self.sftp_password}')
        time.sleep(2)

        print('entered all creds')

        # submit data
        await self.page.keyboard.press('Enter')
        print('pressed enter key')

        

        # update self.process with info_url
        info_url = self.page.url
        await self.update_process(info_url=info_url)
        

        done = False
        done_text = 'Your migration is complete!'
        new_progress = 0
        print(f'current url -> {self.page.url}')
        while not done:
            
            # checking for progres bar
            try:
                raw_progress = await self.page.xpath('//*[@id="app"]/span/div[2]/span/div/div/div/div/div/div[3]/div[4]/div[2]')
                new_progress = await (await raw_progress[0].getProperty('textContent')).jsonValue()
                new_progress = float(new_progress.split('%')[0])
            except Exception as e: 
                # print(e)
                pass
            

            # update self.process
            await self.update_process(progress=new_progress)

            # check if new_progress is 100%
            page_content = await self.page.content()
            if new_progress >= 100 or done_text in page_content:
                time_completed = datetime.now()
                await self.update_process(successful=True, time_completed=time_completed, progress=100)
                done = True

            # checking for process errors
            if 'alert alert-danger' in page_content:
                done = True
                time_completed = datetime.now()
                await self.update_process(time_completed=time_completed)
                print('found an error - ending process')
                return False

            time.sleep(1)


        return True






    async def run_full(self, plugin_name):
        data = await self.login()
        data = await self.begin_lang_check()
        data = await self.install_plugin(plugin_name)
        # data = await self.end_lang_check()
        data = await self.launch_migration()
        data = await self.run_migration()
        await self.driver.close()
        return data

