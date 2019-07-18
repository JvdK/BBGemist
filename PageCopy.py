import logging
import os
import posixpath
import re
from getpass import getpass

import requests
from bs4 import BeautifulSoup

import Config
import Utils
from Downloader import Downloader

base_url = "https://blackboard.utwente.nl"


class PageCopy(Downloader):
    username = None
    password = None

    def __init__(self):
        logging.debug("--- Initialising Downloader ---")

        user_file = Config.CACHE_PATH + "user.txt"
        user_data = None
        if os.path.isfile(user_file):
            logging.debug('Reading user credentials file')
            user_data = Utils.data(file=user_file)
            self.username = user_data['username']
            self.password = user_data['password']
            logging.debug('Read user credentials file')
            message = "Logging in to Blackboard using stored credentials, please wait..."
        else:
            message = "Please login to Blackboard"
            print(message)
            print("=" * len(message))
            print()

            if self.username is None:
                logging.debug('User will type username now...')
                self.username = input("Please type your username and hit [Enter]:\n> ")
                logging.debug("User typed username.")
                print()
            if self.password is None:
                logging.debug("User will type password now...")
                print("Please type your password (not visible) and hit [Enter]:\n")
                self.password = getpass("> ")
                logging.debug("User typed password.")
                print()

            message = "Logging in to Blackboard, please wait..."
        print(message)
        print()

        self.session = requests.session()

        self.files = []

        self.login()

        if user_data is None:
            logging.debug('User will answer store credentials question now...')
            question = "Would you like to store your credentials? (unsafe, username and password will be visible)"
            answer = Utils.yes_or_no(question)
            logging.debug(f'User answered {answer}')
            if answer:
                data = {
                    'username': self.username,
                    'password': self.password
                }
                Utils.write(user_file, data)
                logging.info('Wrote user credentials to cache')

        self.get_courses()

        print("Done!")

    def login(self):
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

    def get_courses(self):
        page_url = f"{base_url}/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1"
        r = self.session.get(page_url)
        soup = Utils.soup(string=r.text)
        self.load_courses(soup)
        self.process_page(soup)
        Utils.write(Config.DOWNLOAD_PATH + "Courses.html", soup.prettify())

    def load_courses(self, soup: BeautifulSoup):
        # Load the data for the My Courses tab
        tab_url = f"{base_url}/webapps/portal/execute/tabs/tabAction"
        tab_data = {
            'action': 'refreshAjaxModule',
            'modId': '4_1',
            'tabId': '_2_1',
            'tab_tab_group_id': '_2_1'
        }
        r = self.session.post(tab_url, data=tab_data)
        tab_soup = Utils.soup(string=r.text)
        content_soup = Utils.soup(string=tab_soup.find('contents').text)
        self.remove_scripts(content_soup)
        soup.find('div', id='div_4_1').replace_with(content_soup)

        # The Course Catalogue won't be downloaded so the tab can be deleted
        soup.find('div', id='column1').decompose()

    def process_page(self, soup: BeautifulSoup):
        self.remove_scripts(soup)
        self.replace_local_urls(soup, 'link', 'href')
        self.replace_local_urls(soup, 'img', 'src')
        self.replace_style_tags(soup)

    @staticmethod
    def remove_scripts(soup: BeautifulSoup):
        for script in soup.find_all('script'):
            script.decompose()

    def replace_local_urls(self, soup: BeautifulSoup, tag: str, attr: str):
        for element in soup.find_all(tag, {attr: True}):
            # Only replace local urls
            url = element[attr]
            if url.startswith('/'):
                path = self.download_local_file(url)[1:]
                element[attr] = path

    def download_local_file(self, url: str):
        local_path = self.strip_url(url)
        full_path = Config.DOWNLOAD_PATH + local_path[1:]
        if not os.path.isfile(full_path):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            r = self.session.get(base_url + url)
            # CSS needs to be rewritten before writing to file
            if os.path.splitext(full_path)[1] == '.css':
                local_dir = posixpath.dirname(local_path)
                css = self.replace_css_urls(r.text, local_dir)
                with open(full_path, "w", encoding='utf-8') as f:
                    f.write(css)
            else:
                with open(full_path, "wb") as f:
                    f.write(r.content)
        return local_path

    @staticmethod
    def strip_url(url: str):
        if '#' in url:
            url = url[:url.find('#')]
        if '?' in url:
            url = url[:url.find('?')]
        return url

    def replace_style_tags(self, soup: BeautifulSoup):
        for tag in soup.find_all('style', {'type': 'text/css'}):
            new_css = self.replace_css_urls(tag.text)
            tag.string.replace_with(new_css)

    def replace_css_urls(self, css: str, folder: str = ''):
        def url_replace(match):
            url = match.group(2).strip()
            if url.lower() == 'none':
                return match.group(0)
            if url.startswith(base_url):
                url = url[len(base_url):]
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
