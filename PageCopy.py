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
website_path = Config.DOWNLOAD_PATH + "website/"


class PageCopy(Downloader):
    username = None
    password = None

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
        self.get_all_courses(soup)
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

    def get_all_courses(self, soup: BeautifulSoup):
        logging.info("Retrieving all courses")
        courses = soup.find('div', id='_4_1termCourses_noterm').find_all('li')
        for course in courses:
            link = course.find('a')
            new_url = self.get_course_page(link['href'].strip())
            link['href'] = new_url
        logging.info("Retrieved all courses")

    #
    # Individual courses
    #

    def get_course_page(self, page_url):
        logging.info(f"Retrieving course: {page_url}")
        url = base_url + page_url
        r = self.session.get(url)
        soup = Utils.soup(string=r.text)
        course_name = soup.find('a', id='courseMenu_link').text.strip()
        logging.info(f"Retrieved course: {page_url} - {course_name}")
        print(f"Retrieving course: {course_name}...")
        # Remove illegal filename characters
        course_name = re.sub(r'[<>:"/\\|?*]', '', course_name)
        current_page = soup.find('span', id='pageTitleText').text.strip()
        file_path = f"{course_name} - {current_page}.html"
        self.process_page(soup)
        Utils.write(website_path + file_path, soup.prettify())
        logging.info(f"Stored course: {course_name}")
        return file_path

    #
    # General page processing
    #

    def process_page(self, soup: BeautifulSoup):
        self.remove_scripts(soup)
        self.replace_local_urls(soup, 'link', 'href')
        self.replace_local_urls(soup, 'img', 'src')
        self.replace_local_urls(soup, 'script', 'src')
        self.replace_style_tags(soup)
        self.cleanup_page(soup)
        self.replace_navbar(soup)

    @staticmethod
    def remove_scripts(soup: BeautifulSoup):
        for script in soup.find_all('script'):
            # Keep scripts responsible for collapsing menu bar
            if script.has_attr('src'):
                if not any(name in script['src'] for name in ['fastinit.js', 'prototype.js', 'page.js']):
                    script.decompose()
            else:
                if 'PageMenuToggler' in script.text:
                    for line in script.text.split('\n'):
                        if 'PageMenuToggler' in line:
                            script.string.replace_with(line.strip())
                            break
                else:
                    script.decompose()

    def replace_local_urls(self, soup: BeautifulSoup, tag: str, attr: str):
        for element in soup.find_all(tag, {attr: True}):
            url = element[attr]
            if url.startswith(base_url):
                url = url[len(base_url):]
            # Only replace local urls
            if self.is_local_url(url):
                path = self.download_local_file(url)[1:]
                element[attr] = path

    def replace_style_tags(self, soup: BeautifulSoup):
        for tag in soup.find_all('style', {'type': 'text/css'}):
            new_css = self.replace_css_urls(tag.text)
            tag.string.replace_with(new_css)

    @staticmethod
    def cleanup_page(soup: BeautifulSoup):
        for tag in soup.find_all(class_='hideFromQuickLinks'):
            tag.decompose()
        for tag in soup.find_all(class_='edit_controls'):
            tag.decompose()
        soup.find('div', id='quickLinksLightboxDiv').decompose()
        soup.find('div', id='quick_links_wrap').decompose()
        soup.find('div', class_='global-nav-bar-wrap').decompose()

    @staticmethod
    def replace_navbar(soup: BeautifulSoup):
        soup.find('td', id='My Blackboard').decompose()
        soup.find('td', id='Courses.label').find('a')['href'] = 'Courses.html'
        soup.find('td', id='Organisations').find('a')['href'] = 'Organisations.html'
        grades = soup.find('td', id='Support')
        grades.find('a')['href'] = 'Grades.html'
        grades.find('span').string.replace_with('Grades')

    def download_local_file(self, url: str):
        local_path = self.strip_url(url)
        full_path = website_path + local_path[1:]
        if not os.path.isfile(full_path):
            r = self.session.get(base_url + url)
            # Update path in case of redirects
            if len(r.history) > 0:
                url = r.url
                if url.startswith(base_url):
                    url = url[len(base_url):]
                local_path = self.strip_url(url)
                full_path = website_path + local_path[1:]
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
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

    def replace_css_urls(self, css: str, folder: str = ''):
        def url_replace(match):
            url = match.group(2).strip()
            if url.startswith(base_url):
                url = url[len(base_url):]
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

    @staticmethod
    def is_local_url(url: str):
        # Assumes urls starting with the base_url have been stripped
        return not (url == 'none' or url.startswith('http:') or url.startswith('https:') or url.startswith('data:'))

    @staticmethod
    def strip_url(url: str):
        if '#' in url:
            url = url[:url.find('#')]
        if '?' in url:
            url = url[:url.find('?')]
        return url
