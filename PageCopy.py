import logging
import os
import posixpath
import re
import urllib.parse
from getpass import getpass

import requests
from bs4 import BeautifulSoup
from requests import Response

import Config
import Utils
from Downloader import Downloader

base_url = "https://blackboard.utwente.nl"
website_path = Config.DOWNLOAD_PATH + "website/"


class PageCopy(Downloader):
    username = None
    password = None
    url_dict = {
        'Courses.html': '/Courses.html',
        'Organisations.html': '/Organisations.html',
        'Grades.html': '/Grades.html'
    }
    page_titles = set()

    def __init__(self):
        logging.info("--- Initialising Downloader ---")

        user_file = Config.CACHE_PATH + "user.txt"
        user_data = None
        if os.path.isfile(user_file):
            logging.info('Reading user credentials file')
            user_data = Utils.data(file=user_file)
            self.username = user_data['username']
            self.password = user_data['password']
            logging.info('Read user credentials file')
            message = "Logging in to Blackboard using stored credentials, please wait..."
        else:
            message = "Please login to Blackboard"
            print(message)
            print("=" * len(message))
            print()
            if self.username is None:
                logging.info('User will type username now...')
                self.username = input("Please type your username and hit [Enter]:\n> ")
                logging.info("User typed username.")
                print()
            if self.password is None:
                logging.info("User will type password now...")
                print("Please type your password (not visible) and hit [Enter]:\n")
                self.password = getpass("> ")
                logging.info("User typed password.")
                print()
            message = "Logging in to Blackboard, please wait..."
        print(message)

        self.session = requests.session()
        self.files = []
        self.login()

        if user_data is None:
            logging.info('User will answer store credentials question now...')
            question = "Would you like to store your credentials? (unsafe, username and password will be visible)"
            answer = Utils.yes_or_no(question)
            logging.info(f'User answered {answer}')
            if answer:
                data = {
                    'username': self.username,
                    'password': self.password
                }
                Utils.write(user_file, data)
                logging.info('Wrote user credentials to cache')

        self.get_cdn_images()
        self.get_courses_page()
        self.create_index_page()
        print("Done!")

    def login(self):
        logging.info('Logging in to Blackboard')
        login_url = f"{base_url}/webapps/login/"

        payload = {
            'user_id': self.username,
            'password': self.password,
            'login': 'Login',
            'action': 'login',
            'new_loc': ''
        }

        r = self.session.post(login_url, data=payload)

        if 'webapps/portal/execute/defaultTab' in r.text:
            logging.info('Login successful!')
            print("Login successful!")
        else:
            logging.critical('Login failed!')
            print("Login failed, please check your credentials or refer to the README.md file!")
            exit()

    def get_cdn_images(self):
        self.download_local_file('/images/ci/mybb/x_btn.png')

    @staticmethod
    def create_index_page():
        logging.info("Creating index page")
        print("Creating index page...")
        index_content = '<meta http-equiv="Refresh" content="0; url=website/Courses.html"/>'
        Utils.write(Config.DOWNLOAD_PATH + "index.html", index_content)
        logging.info("Created index page")

    #
    # Overview pages
    #

    def get_courses_page(self):
        logging.info("Retrieving courses page")
        print("Retrieving courses...")
        page_url = f"{base_url}/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1"
        r = self.session.get(page_url)
        url_dir = posixpath.dirname(self.strip_url(r.url))
        soup = Utils.soup(string=r.text)
        logging.info("Retrieved courses page")
        self.process_page(soup, url_dir)
        Utils.write(website_path + "Courses.html", soup.prettify())
        logging.info("Stored courses page")

    #
    # General page processing
    #

    def process_page(self, soup: BeautifulSoup, url_dir: str):
        self.load_tabs(soup)
        self.load_course_information(soup)
        self.load_discussion_board(soup)
        self.remove_scripts(soup)
        self.cleanup_page(soup)
        self.replace_navbar(soup)
        self.replace_local_urls(soup, 'img', 'src', url_dir)
        self.replace_local_urls(soup, 'script', 'src', url_dir)
        self.replace_local_urls(soup, 'link', 'href', url_dir)
        self.replace_style_tags(soup, url_dir)
        self.replace_local_urls(soup, 'a', 'href', url_dir)
        self.replace_onclick(soup)

    def load_tabs(self, soup: BeautifulSoup):
        tab_url = '/webapps/portal/execute/tabs/tabAction'
        full_url = base_url + tab_url
        for script in soup.find_all('script', text=True):
            script = script.text
            if tab_url in script:
                div_id = re.search(r"\$\('([^']*)'\)", script).group(1)
                parameters = re.search(r"parameters: '([^,']*)',", script).group(1)
                data = urllib.parse.parse_qs(parameters)
                r = self.session.post(full_url, data=data)
                tab_soup = Utils.soup(string=r.text)
                content_soup = Utils.soup(string=tab_soup.find('contents').text)
                soup.find('div', id=div_id).replace_with(content_soup)

    def load_course_information(self, soup: BeautifulSoup):
        url_part = '/webapps/utnl-OsirisCursusinformatie-bb_bb60/showCourseInformationJsAsync.do'
        for script in soup.find_all('script', {'src': True}):
            if url_part in script['src']:
                r = self.session.get(base_url + script['src'])
                course_information = re.search(r"var html = '(.*)';", r.text).group(1)
                course_information = course_information.encode('utf-8').decode('unicode_escape').replace('\\/', '/')
                course_information_soup = Utils.soup(string=course_information)
                soup.find('div', id='osirisCursusInformatie_contentDiv').replace_with(course_information_soup)

    def load_discussion_board(self, soup: BeautifulSoup):
        for script in soup.find_all('script', text=True):
            script = script.text
            if 'treeUrl' in script:
                tree_url = re.search(r'var treeUrl = "([^"]*)";', script).group(1)
                r = self.session.get(base_url + tree_url)
                tree_soup = Utils.soup(string=r.text)
                soup.find('div', id='tree').replace_with(tree_soup)

    def remove_scripts(self, soup: BeautifulSoup):
        # TODO: Don't include all ngui scripts
        allowed_scripts = ['cdn.js', 'fastinit.js', 'prototype.js', 'ngui', 'mygrades.js',
                           'effects.js', 'grade_assignment.js', 'inline-grading']
        allowed_keywords = ['page.bundle.addKey', 'PageMenuToggler', 'PaletteController', 'mygrades', 'gradeAssignment',
                            'collapsiblelist', 'postInit']
        for script in soup.find_all('script'):
            if script.has_attr('src'):
                # Keep allowed scripts
                if not any(name in script['src'] for name in allowed_scripts):
                    script.decompose()
            else:
                def contains_allowed_keyword(text):
                    return any(keyword in text for keyword in allowed_keywords)

                # Keep lines containing allowed keywords
                if contains_allowed_keyword(script.text):
                    lines = script.text.split('\n')
                    allowed_lines = [self.rewrite_line(line) for line in lines if contains_allowed_keyword(line)]
                    new_script = '\n'.join(allowed_lines)
                    script.string.replace_with(new_script)
                else:
                    script.decompose()
        # Add fake DWR to prevent errors
        self.add_fake_dwr(soup)

    def rewrite_line(self, line: str):
        line = line.strip()
        # Special case for grade assignments
        if 'gradeAssignment.init' in line:
            def url_replace(match):
                url = self.strip_url(match.group(2))
                path = self.download_local_file(url)[1:]
                return match.group(1) + path + match.group(3)

            line = re.sub(r'("downloadUrl":")(.*?)(",)', url_replace, line)
        return line

    @staticmethod
    def add_fake_dwr(soup):
        script = soup.new_tag('script')
        script.string = '''
        var UserDataDWRFacade = {
            getStringPermScope: function(){},
            setStringPermScope: function(){},
            getStringTempScope: function(){},
            setStringTempScope: function(){}
        }
        '''
        soup.head.insert(0, script)

    @staticmethod
    def cleanup_page(soup: BeautifulSoup):
        def decompose(tags):
            for tag in tags:
                tag.decompose()

        decompose(soup.find_all(class_='hideFromQuickLinks'))  # Quick Links
        decompose(soup.find_all(class_='edit_controls'))  # Edit settings
        decompose(soup.find_all(class_='contextMenuContainer'))  # Context menu
        decompose(soup.find_all(id='quickLinksLightboxDiv'))  # Quick links
        decompose(soup.find_all(id='quick_links_wrap'))  # Quick links
        decompose(soup.find_all(class_='global-nav-bar-wrap'))  # User menu
        decompose(soup.find_all(id='breadcrumb_controls_id'))  # Navigation helper
        decompose(soup.find_all(class_='courseArrow'))  # Courses menu
        decompose(soup.find_all(class_='actionBarMicro'))  # Courses menu
        decompose(soup.find_all(class_='localViewToggle'))  # Courses menu
        decompose(soup.find_all(id='controlPanelPalette'))  # Course management panel
        decompose(soup.find_all(class_='eudModule'))  # Home page modules
        decompose(soup.find_all(id='actionbar'))  # Action bar
        decompose(soup.find_all(class_='subActionBar'))  # Action bar
        decompose(soup.find_all(class_='rumble'))  # Action bar
        decompose(soup.find_all(class_='rumble_top'))  # Action bar
        decompose(soup.find_all(class_='dbThreadFooter'))  # Thread footer
        decompose(soup.find_all(id='module:_28_1'))  # Course Catalogue
        decompose(soup.find_all(id='module:_493_1'))  # Search course catalogue
        decompose(soup.find_all(id='copyright'))  # Copyright at page bottom
        decompose(soup.find_all(class_='taskbuttondiv_wrapper'))  # Task submission buttons
        decompose(soup.find_all(id='step2'))  # Assignment submission
        decompose(soup.find_all(id='step3'))  # Add comments
        decompose(soup.find_all(class_='submitStepBottom'))  # Assignment submission buttons
        decompose(soup.find_all(id='iconLegendLinkDiv'))  # Icon legend
        decompose(soup.find_all(class_='containerOptions'))  # Action bar options
        decompose(soup.find_all(id='listContainer_showAllButton'))  # Discussion Board show all
        decompose(soup.find_all(id='listContainer_openpaging'))  # Discussion Board edit
        decompose(soup.find_all(id='listContainer_editpaging'))  # Discussion Board edit
        decompose(soup.find_all(id='listContainer_nav_batch_top'))  # File exchange delete
        decompose(soup.find_all(id='listContainer_nav_batch_bot'))  # File exchange delete
        decompose(soup.find_all(id='listContainer_showAllButton'))  # Discussion board show all
        decompose(soup.find_all(id='listContainer_openpaging'))  # Discussion board edit paging
        decompose(soup.find_all(id='top_list_action_bar'))  # Discussion Board action bar
        decompose(soup.find_all(id='bottom_list_action_bar'))  # Discussion Board action bar
        decompose(soup.find_all(class_='renameCourseToc'))  # Rename menu
        decompose(soup.find_all(id='moduleReorderControls'))  # Module reordering
        decompose(soup.find_all(id='reorderControlsannouncementList'))  # Announcement reordering
        decompose(soup.find_all(class_='quickAddPal'))  # Adding items to course
        decompose(soup.find_all(id='courseMenuPalette_reorderControls'))  # Course menu reordering
        decompose(soup.find_all(class_='reorder'))  # Course menu reordering
        decompose(soup.find_all('h2', class_='navDivider', text=re.compile('Course Management')))  # Course management
        decompose(soup.find_all('input', type='hidden'))  # Hidden inputs

        def decompose_url(url_part):
            for a in soup.find_all('a', {'href': True}):
                if url_part in a['href']:
                    parent = a.parent
                    a.decompose()
                    while parent and not parent.contents:
                        new_parent = parent.parent
                        parent.decompose()
                        parent = new_parent

        decompose_url('tool_id=_1842_1')  # Unenroll
        decompose_url('tool_id=_134_1')  # Email
        decompose_url('tool_id=_115_1')  # Email
        decompose_url('displayEmail')  # Email
        decompose_url('viewExtendedHelp')  # Help pages
        decompose_url('launchAssessment')  # Assessments
        decompose_url('groupContentList')  # Groups
        decompose_url('groupInventoryList')  # Group management

        # TODO: Edit mode pages

        def delete_attribute(tags, attribute):
            for tag in tags:
                del tag[attribute]

        delete_attribute(soup.find_all('a', class_='sortheader'), 'href')  # Column sorting

        def delete_url(url_part):
            for a in soup.find_all('a', {'href': True}):
                if url_part in a['href']:
                    del a['href']

        delete_url('oslt-signUpList-bb_bb60')  # Sign up lists

        def remove_class(class_):
            for tag in soup.find_all(class_=class_):
                tag['class'].remove(class_)

        remove_class('ineditmode')  # Edit mode markup
        remove_class('reorderableModule')  # Edit mode markup
        remove_class('dragHandle')  # Edit mode markup

    @staticmethod
    def replace_navbar(soup: BeautifulSoup):
        if soup.find('div', id='globalNavPageNavArea'):
            soup.find('td', id='My Blackboard').decompose()
            soup.find('td', id='Courses.label').find('a')['href'] = 'Courses.html'
            soup.find('td', id='Organisations').find('a')['href'] = 'Organisations.html'
            grades = soup.find('td', id='Support')
            grades.find('a')['href'] = 'Grades.html'
            grades.find('span').string.replace_with('Grades')

    def replace_onclick(self, soup):
        for a in soup.find_all('a', {'onclick': True}):
            if 'mygrades.loadContentFrame' in a['onclick']:
                href = re.search(r"mygrades.loadContentFrame\('(.*)'\)", a['onclick']).group(1)
                path = self.download_local_file(href)[1:]
                a['href'] = path
                del a['onclick']
            elif 'gradeAssignment.inlineView' in a['onclick']:
                del a['href']
                del a['onclick']

    def replace_local_urls(self, soup: BeautifulSoup, tag: str, attr: str, url_dir: str):
        for element in soup.find_all(tag, {attr: True}):
            url = self.strip_url(element[attr].strip())
            # Only replace local urls
            if self.is_local_url(url):
                if not url.startswith('/') and url not in ['Courses.html', 'Organisations.html', 'Grades.html']:
                    url = f'{url_dir}/{url}'
                path = self.download_local_file(url)[1:]
                element[attr] = path

    def replace_style_tags(self, soup: BeautifulSoup, url_dir: str):
        # Replace local css
        for tag in soup.find_all('style', {'type': 'text/css'}):
            new_css = self.replace_css_urls(tag.text, url_dir)
            tag.string.replace_with(new_css)

        # Replace inline css
        for tag in soup.find_all(True, {'style': True}):
            new_style = self.replace_css_urls(tag['style'], url_dir)
            tag['style'] = new_style

    def download_local_file(self, url: str):
        # TODO: Order files by course
        url = self.strip_url(url)
        # Check if url already has been downloaded
        if url in self.url_dict:
            return self.url_dict[url]

        # Check if file already exists
        local_path = self.url_to_path(url)
        full_path = self.get_full_path(local_path)
        if os.path.isfile(full_path):
            self.update_url_dict(local_path, url=url)
            return local_path

        with self.session.get(base_url + url, stream=True) as r:
            url = self.strip_url(r.url)

            # Check if (potentially redirected) url already has been downloaded
            if url in self.url_dict or any(redirect.url in self.url_dict for redirect in r.history):
                # Store the redirected urls as well
                self.update_url_dict(self.url_dict[url], url=url, request=r)
                return self.url_dict[url]

            # Check if (potentially redirected) file already exists
            if r.status_code == 404:
                local_path = '/404.html'
            else:
                local_path = self.url_to_path(url)
            full_path = self.get_full_path(local_path)
            if os.path.isfile(full_path):
                self.update_url_dict(local_path, url=url, request=r)
                return local_path

            is_html = 'html' in r.headers['content-type']
            soup = None

            # HTML paths are based on page title
            if is_html:
                soup = Utils.soup(string=r.text)
                if r.status_code != 404:
                    local_path = self.generate_page_title(soup)
                    full_path = self.get_full_path(local_path)

            print(f'Retrieving: {local_path}')

            self.update_url_dict(local_path, url=url, request=r)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # HTML pages need te be processed
            if is_html:
                url_dir = posixpath.dirname(url)
                self.process_page(soup, url_dir)
                Utils.write(full_path, soup.prettify())
            # CSS urls need to be rewritten
            elif os.path.splitext(full_path)[1] == '.css':
                url_dir = posixpath.dirname(url)
                local_dir = posixpath.dirname(local_path)
                css = self.replace_css_urls(r.text, url_dir, local_dir)
                with open(full_path, "w", encoding='utf-8') as f:
                    f.write(css)
            # Other files can be stored without processing
            else:
                with open(full_path, "wb") as f:
                    # Use chunks in case of very large files
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            # TODO: Readd hash to url
            return local_path

    def generate_page_title(self, soup):
        title = soup.find('title')
        if title:
            # Remove illegal filename characters
            title = re.sub(r'[<>:"/\\|?*]', '', title.text)
        else:
            title = 'unknown'

        local_path = None
        done = False
        counter = 0
        while not done:
            local_path = f'/{title}.html' if counter == 0 else f'/{title} ({counter}).html'
            if local_path in self.page_titles:
                counter += 1
            else:
                self.page_titles.add(local_path)
                done = True
        return local_path

    def replace_css_urls(self, css: str, url_dir: str, local_dir: str = '/'):
        def url_replace(match):
            url = match.group(2).strip()
            url = self.strip_url(url)
            if not self.is_local_url(url):
                return match.group(0)
            full_url = posixpath.normpath(posixpath.join(url_dir, url))
            path = self.download_local_file(full_url)
            relative_path = posixpath.relpath(path, local_dir)
            return match.group(1) + relative_path + match.group(3)

        result = re.sub(r"(url\(['\"]?)(.*?)(['\"]?\))", url_replace, css)
        return result

    def update_url_dict(self, path: str, url: str = None, request: Response = None):
        if url:
            self.url_dict[url] = path
        if request:
            # Store the redirected urls as well
            for redirect in request.history:
                redirected_url = self.strip_url(redirect.url)
                self.url_dict[redirected_url] = path

    @staticmethod
    def get_full_path(local_path):
        return website_path + local_path[1:]

    @staticmethod
    def is_local_url(url: str):
        url = url.lower()
        return url.startswith(base_url) or not (
                url == 'none' or
                url.startswith('#') or
                url.startswith('%') or
                url.startswith('mailto:') or
                url.startswith('ftp:') or
                url.startswith('data:') or
                url.startswith('javascript:') or
                url.startswith('http:') or
                url.startswith('https:')
        )

    @staticmethod
    def strip_url(url: str):
        if url.startswith(base_url):
            url = url[len(base_url):]
        return url

    @staticmethod
    def url_to_path(url: str):
        if '/webapps/assignment/download' in url:
            filename = re.search(r"fileName=([^&]*)", url).group(1)
            path = f'/assignments/{filename}'
        else:
            if '#' in url:
                url = url[:url.find('#')]
            if '?' in url:
                url = url[:url.find('?')]
            path = url
        path = urllib.parse.unquote(path)
        return path
