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
        url_dir = posixpath.dirname(self.strip_base_url(r.url))
        soup = Utils.soup(string=r.text)
        logging.info("Retrieved courses page")
        self.process_page(soup, url_dir)
        Utils.write(website_path + "Courses.html", soup.prettify())
        logging.info("Stored courses page")

    #
    # General page processing
    #

    def process_page(self, soup: BeautifulSoup, local_dir: str):
        self.load_tabs(soup)
        self.load_course_information(soup)
        self.remove_scripts(soup)
        self.cleanup_page(soup)
        self.replace_navbar(soup)
        self.replace_local_urls(soup, 'img', 'src', local_dir)
        self.replace_local_urls(soup, 'script', 'src', local_dir)
        self.replace_local_urls(soup, 'link', 'href', local_dir)
        self.replace_style_tags(soup)
        self.replace_local_urls(soup, 'a', 'href', local_dir)
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

    def remove_scripts(self, soup: BeautifulSoup):
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
                url = self.strip_base_url(match.group(2))
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
        soup.append(script)

    @staticmethod
    def cleanup_page(soup: BeautifulSoup):
        def decompose(tags):
            for tag in tags:
                tag.decompose()

        decompose(soup.find_all(class_='hideFromQuickLinks'))
        decompose(soup.find_all(class_='edit_controls'))
        decompose(soup.find_all('div', id='quickLinksLightboxDiv'))
        decompose(soup.find_all('div', id='quick_links_wrap'))
        decompose(soup.find_all('div', class_='global-nav-bar-wrap'))
        decompose(soup.find_all('div', id='breadcrumb_controls_id'))
        decompose(soup.find_all('div', class_='courseArrow'))
        decompose(soup.find_all('div', class_='actionBarMicro'))
        decompose(soup.find_all('div', class_='localViewToggle'))
        decompose(soup.find_all('div', id='controlPanelPalette'))
        decompose(soup.find_all('div', class_='eudModule'))
        decompose(soup.find_all('div', id='actionbar'))
        decompose(soup.find_all('div', id='module:_28_1'))  # Course Catalogue
        decompose(soup.find_all('div', id='module:_493_1'))  # Search course catalogue
        decompose(soup.find_all('div', id='copyright'))  # Copyright at page bottom
        decompose(soup.find_all('div', class_='taskbuttondiv_wrapper'))  # Task submission buttons
        decompose(soup.find_all('div', id='step2'))  # Assignment submission
        decompose(soup.find_all('div', id='step3'))  # Add comments
        decompose(soup.find_all('div', class_='submitStepBottom'))  # Assignment submission buttons
        decompose(soup.find_all('div', id='iconLegendLinkDiv'))  # Icon legend

        def decompose_url(url_part):
            for a in soup.find_all('a', {'href': True}):
                if url_part in a['href']:
                    a.decompose()

        decompose_url('tool_id=_115_1')  # Email
        decompose_url('tool_id=_119_1')  # TODO: Fix discussion boards
        decompose_url('tool_id=_2134_1')  # TODO: Fix discussion boards
        decompose_url('viewExtendedHelp')  # Help pages
        # TODO: Edit mode pages

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
            url = self.strip_base_url(element[attr].strip())
            # Only replace local urls
            if self.is_local_url(url):
                if not url.startswith('/') and url not in ['Courses.html', 'Organisations.html', 'Grades.html']:
                    url = f'{url_dir}/{url}'
                path = self.download_local_file(url)[1:]
                element[attr] = path

    def replace_style_tags(self, soup: BeautifulSoup):
        # Replace local css
        for tag in soup.find_all('style', {'type': 'text/css'}):
            new_css = self.replace_css_urls(tag.text)
            tag.string.replace_with(new_css)

        # Replace inline css
        for tag in soup.find_all(True, {'style': True}):
            new_style = self.replace_css_urls(tag['style'])
            tag['style'] = new_style

    def download_local_file(self, url: str):
        # TODO: Order files by course
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
            url = self.strip_base_url(r.url)

            # Check if (potentially redirected) url already has been downloaded
            if url in self.url_dict:
                # Store the redirected urls as well
                self.update_url_dict(self.url_dict[url], request=r)
                return self.url_dict[url]

            # Check if (potentially redirected) file already exists
            local_path = self.url_to_path(url)
            full_path = self.get_full_path(local_path)
            if os.path.isfile(full_path):
                self.update_url_dict(local_path, url=url, request=r)
                return local_path

            is_html = 'html' in r.headers['content-type']
            soup = None

            # HTML paths are based on page title, file paths are based on url path
            if is_html:
                soup = Utils.soup(string=r.text)
                local_path = self.generate_page_title(soup)
            else:
                local_path = self.url_to_path(url)

            print(f'Retrieving: {local_path}')
            full_path = self.get_full_path(local_path)
            self.update_url_dict(local_path, url=url, request=r)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # HTML pages need te be processed
            if is_html:
                url_dir = posixpath.dirname(url)
                self.process_page(soup, url_dir)
                Utils.write(full_path, soup.prettify())
            # CSS urls need to be rewritten
            elif os.path.splitext(full_path)[1] == '.css':
                local_dir = posixpath.dirname(local_path)
                css = self.replace_css_urls(r.text, local_dir)
                with open(full_path, "w", encoding='utf-8') as f:
                    f.write(css)
            # Other files can be stored without processing
            else:
                with open(full_path, "wb") as f:
                    # Use chunks in case of very large files
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

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

    def replace_css_urls(self, css: str, folder: str = '/'):
        def url_replace(match):
            url = match.group(2).strip()
            url = self.strip_base_url(url)
            if not self.is_local_url(url):
                return match.group(0)
            url = posixpath.normpath(posixpath.join(folder, url))
            path = self.download_local_file(url)
            relative_path = posixpath.relpath(path, folder)
            return match.group(1) + relative_path + match.group(3)

        result = re.sub(r"(url\(['\"]?)(.*?)(['\"]?\))", url_replace, css)
        return result

    def update_url_dict(self, path: str, url: str = None, request: Response = None):
        if url:
            self.url_dict[url] = path
        if request:
            # Store the redirected urls as well
            for redirect in request.history:
                redirected_url = self.strip_base_url(redirect.url)
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
                url.startswith('data:') or
                url.startswith('javascript:') or
                url.startswith('http:') or
                url.startswith('https:')
        )

    @staticmethod
    def strip_base_url(url: str):
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
