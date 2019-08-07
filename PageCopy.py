import logging
import os
import posixpath
import re
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

    @staticmethod
    def create_index_page():
        logging.info("Creating index page")
        print("Creating index page...")
        index_content = '<meta http-equiv="Refresh" content="0; url=website/Courses.html"/>'
        Utils.write(Config.DOWNLOAD_PATH + "index.html", index_content)
        logging.info("Created index page")

    #
    # Courses overview
    #

    def get_courses_page(self):
        logging.info("Retrieving courses page")
        print("Retrieving courses...")
        page_url = f"{base_url}/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1"
        r = self.session.get(page_url)
        soup = Utils.soup(string=r.text)
        logging.info("Retrieved courses page")
        self.load_courses_tab(soup)
        self.process_page(soup)
        Utils.write(website_path + "Courses.html", soup.prettify())
        logging.info("Stored courses page")

    def load_courses_tab(self, soup: BeautifulSoup):
        # Load the data for the My Courses tab
        logging.info("Retrieving My Courses tab")
        tab_url = f"{base_url}/webapps/portal/execute/tabs/tabAction"
        tab_data = {
            'action': 'refreshAjaxModule',
            'modId': '4_1',
            'tabId': '_2_1',
            'tab_tab_group_id': '_2_1'
        }
        r = self.session.post(tab_url, data=tab_data)
        tab_soup = Utils.soup(string=r.text)
        logging.info("Retrieved My Courses tab")
        content_soup = Utils.soup(string=tab_soup.find('contents').text)
        self.remove_scripts(content_soup)
        soup.find('div', id='div_4_1').replace_with(content_soup)

        # The Course Catalogue won't be downloaded so the tab can be deleted
        soup.find('div', id='column1').decompose()
        soup.find('div', id='content').find('style').string.replace_with('#column0{width: 100%;}')
        logging.info("Processed My Courses tab")

    #
    # General page processing
    #

    def process_page(self, soup: BeautifulSoup):
        self.remove_scripts(soup)
        self.cleanup_page(soup)
        self.replace_navbar(soup)
        self.replace_local_urls(soup, 'img', 'src')
        self.replace_local_urls(soup, 'script', 'src')
        self.replace_local_urls(soup, 'link', 'href')
        self.replace_style_tags(soup)
        self.replace_local_urls(soup, 'a', 'href')

    @staticmethod
    def remove_scripts(soup: BeautifulSoup):
        allowed_scripts = ['fastinit.js', 'prototype.js', 'page.js']
        allowed_keywords = ['page.bundle.addKey', 'PageMenuToggler', 'PaletteController']
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
                    allowed_lines = [line.strip() for line in lines if contains_allowed_keyword(line)]
                    new_script = '\n'.join(allowed_lines)
                    script.string.replace_with(new_script)
                else:
                    script.decompose()

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

    @staticmethod
    def replace_navbar(soup: BeautifulSoup):
        if soup.find('div', id='globalNavPageNavArea'):
            soup.find('td', id='My Blackboard').decompose()
            soup.find('td', id='Courses.label').find('a')['href'] = 'Courses.html'
            soup.find('td', id='Organisations').find('a')['href'] = 'Organisations.html'
            grades = soup.find('td', id='Support')
            grades.find('a')['href'] = 'Grades.html'
            grades.find('span').string.replace_with('Grades')

    def replace_local_urls(self, soup: BeautifulSoup, tag: str, attr: str):
        for element in soup.find_all(tag, {attr: True}):
            url = self.strip_base_url(element[attr].strip())
            # Only replace local urls
            if self.is_local_url(url):
                if not url.startswith('/'):
                    url = '/' + url
                path = self.download_local_file(url)[1:]
                element[attr] = path

    def replace_style_tags(self, soup: BeautifulSoup):
        for tag in soup.find_all('style', {'type': 'text/css'}):
            new_css = self.replace_css_urls(tag.text)
            tag.string.replace_with(new_css)

    def download_local_file(self, url: str):
        # Check if url already has been downloaded
        if url in self.url_dict:
            return self.url_dict[url]

        # Check if file already exists
        local_path = self.strip_url(url)
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
            local_path = self.strip_url(url)
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
                local_path = self.strip_url(url)

            print(f'Retrieving: {local_path}')
            full_path = self.get_full_path(local_path)
            self.update_url_dict(local_path, url=url, request=r)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # HTML pages need te be processed
            if is_html:
                self.process_page(soup)
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

    def replace_css_urls(self, css: str, folder: str = ''):
        def url_replace(match):
            url = match.group(2).strip()
            url = self.strip_base_url(url)
            if not self.is_local_url(url):
                return match.group(0)
            url = posixpath.normpath(posixpath.join(folder, url))
            path = self.download_local_file(url)
            if folder == '':
                path = path[1:]
            else:
                commonpath = posixpath.commonpath([folder, path])
                if commonpath != '/':
                    path = path.replace(commonpath, '')[1:]
                else:
                    path = '../' * folder.count('/') + path[1:]
            return match.group(1) + path + match.group(3)

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
    def strip_url(url: str):
        if '#' in url:
            url = url[:url.find('#')]
        if '?' in url:
            url = url[:url.find('?')]
        return url
