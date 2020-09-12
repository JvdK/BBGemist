import html
import json
import logging
import os
import posixpath
import re
import time
import urllib.parse
from getpass import getpass

import requests
# noinspection PyProtectedMember
from bs4 import BeautifulSoup, Comment, Tag
from requests import Response

import Config
import Utils
from Downloader import Downloader

base_url = 'https://blackboard.utwente.nl'
website_path = Config.DOWNLOAD_PATH + 'website/'


class PageCopy(Downloader):
    username = None
    password = None
    url_dict = {
        'Courses.html': '/Courses.html',
        'Organisations.html': '/Organisations.html',
        'Grades.html': '/Grades.html'
    }
    downloaded_pages = {}
    navigation_stack = []

    def __init__(self):
        logging.info('--- Initialising Downloader ---')

        user_file = Config.CACHE_PATH + 'user.txt'
        user_data = None
        if os.path.isfile(user_file):
            logging.info('Reading user credentials file')
            user_data = Utils.data(file=user_file)
            self.username = user_data['username']
            self.password = user_data['password']
            logging.info('Read user credentials file')
            message = 'Logging in to Blackboard using stored credentials, please wait...'
        else:
            message = 'Please login to Blackboard'
            print(message)
            print('=' * len(message))
            print()
            if self.username is None:
                logging.info('User will type username now...')
                self.username = input('Please type your username and hit [Enter]:\n> ')
                logging.info('User typed username.')
                print()
            if self.password is None:
                logging.info('User will type password now...')
                print('Please type your password (not visible) and hit [Enter]:\n')
                self.password = getpass('> ')
                logging.info('User typed password.')
                print()
            message = 'Logging in to Blackboard, please wait...'
        print(message)

        self.session = requests.session()
        self.files = []
        self.login()

        if user_data is None:
            logging.info('User will answer store credentials question now...')
            question = 'Would you like to store your credentials? (unsafe, username and password will be visible)'
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
        self.get_organisations_page()
        self.get_grades_pages()
        self.create_index_page()
        print('Done!')

    def login(self):
        r = self.session.get('https://blackboard.utwente.nl/webapps/portal/execute/defaultTab')
        soup = Utils.soup(string=r.text)
        value = soup.find('input', attrs={'name': 'blackboard.platform.security.NonceUtil.nonce'})['value']

        logging.info('Logging in to Blackboard')
        login_url = f'{base_url}/webapps/login/'

        payload = {
            'user_id': self.username,
            'password': self.password,
            'login': 'Login',
            'action': 'login',
            'new_loc': '',
            'blackboard.platform.security.NonceUtil.nonce': value
        }

        r = self.session.post(login_url, data=payload)

        if 'webapps/portal/execute/tabs' in r.text:
            logging.info('Login successful!')
            print('Login successful!')
        else:
            logging.critical('Login failed!')
            print('Login failed, please check your credentials or refer to the README.md file!')
            exit()

    def get_cdn_images(self):
        self.download_local_file('/images/ci/mybb/x_btn.png')

    @staticmethod
    def create_index_page():
        logging.info('Creating index page')
        print('Creating index page...')
        index_content = '<meta http-equiv="Refresh" content="0; url=website/Courses.html"/>'
        Utils.write(Config.DOWNLOAD_PATH + 'index.html', index_content)
        logging.info('Created index page')

    #
    # Overview pages
    #
    def get_courses_page(self):
        self.get_overview_page('Courses', '_2_1')

    def get_organisations_page(self):
        self.get_overview_page('Organisations', '_3_1')

    def get_overview_page(self, name: str, tab_group_id: str):
        logging.info(f'Retrieving {name} page')
        print(f'Retrieving {name}...')
        page_url = f'{base_url}/webapps/portal/execute/tabs/tabAction?tab_tab_group_id={tab_group_id}'
        r = self.session.get(page_url)
        url_dir = self.get_url_dir(r.url)
        soup = Utils.soup(string=r.text)
        logging.info(f'Retrieved {name} page')
        soup.find('div', id='column1').decompose()
        self.process_page(soup, url_dir)
        soup.find('div', id='content').find('style').string.replace_with('#column0{width: 100%;}')
        Utils.write(website_path + name + '.html', soup.prettify())
        logging.info(f'Stored {name} page')

    #
    # Grades
    #
    def get_grades_pages(self):
        self.get_grades_overview('Grades', 'mygrades')
        self.get_grades_overview('Grades individual', 'mygrades_d')

    def get_grades_overview(self, name: str, stream_name: str):
        logging.info(f'Retrieving {name} page')
        print(f'Retrieving {name}...')
        url = f'{base_url}/webapps/bb-social-learning-bb_bb60/execute/mybb?cmd=display&toolId=MyGradesOnMyBb_____MyGradesTool'
        r = self.session.get(url)
        url_dir = self.get_url_dir(r.url)
        soup = Utils.soup(string=r.text)
        logging.info(f'Retrieved {name} page')

        self.process_page(soup, url_dir)
        soup.find(id='Support')['class'] = 'active'
        soup.find(id='iframe_wrap')['style'] = 'left: 0px;'
        self.add_window_height_script(soup, 'mybbCanvas')
        inner_name = f'{name} inner'
        soup.find(id='mybbCanvas')['src'] = f'{inner_name}.html'
        Utils.write(website_path + f'{name}.html', soup.prettify())
        self.get_grades_inner(inner_name, stream_name)
        logging.info(f'Retrieved Grades page')

    def get_grades_inner(self, name: str, stream_name: str):
        url = f'{base_url}/webapps/streamViewer/streamViewer?cmd=view&streamName=mygrades&globalNavigation=false'
        r = self.session.get(url)
        url_dir = self.get_url_dir(r.url)
        soup = Utils.soup(string=r.text)

        self.process_page(soup, url_dir)
        self.add_window_height_script(soup, 'right_stream_mygrades')

        grade_filter = soup.find(id='filter_by_mygrades')
        self.add_grade_filter(soup, grade_filter, 'Courses', 'Grades', name == 'Grades inner')
        self.add_grade_filter(soup, grade_filter, 'Individual grades', 'Grades individual',
                              name == 'Grades individual inner')

        script = soup.new_tag('script')
        script.string = '''function clickGrade(e) {
            elements = $("left_stream_mygrades").getElementsByTagName("div");
            for(i = 0; i< elements.length; i++) {
                elements[i].setAttribute("aria_selected", "false");
                elements[i].classList.remove("active_stream_item");
            }
            e.currentTarget.setAttribute("aria_selected", "true");
            e.currentTarget.classList.add("active_stream_item");
            $("right_stream_mygrades").src = e.currentTarget.dataset.path;
        }
        '''
        soup.find('body').append(script)

        rhs = self.download_local_file(f'{base_url}/webapps/streamViewer/streamViewer?cmd=emptyRhs')[1:]
        soup.find(id='right_stream_mygrades')['src'] = rhs

        stream_entries = self.get_stream_entries(stream_name)

        gradelist = soup.find(id='left_stream_mygrades')
        entries = stream_entries['sv_streamEntries']
        if all(self.get_entry_timestamp(entry) >= 0 for entry in entries):
            entries.sort(key=self.get_entry_timestamp)
        else:
            entries.sort(key=self.get_entry_course_id)

        for entry in entries:
            self.add_entry_to_gradelist(soup, gradelist, entry, stream_entries)

        Utils.write(website_path + f'{name}.html', soup.prettify())

    @staticmethod
    def add_grade_filter(soup: BeautifulSoup, grade_filter: Tag, name: str, path: str, this_page: bool):
        li = soup.new_tag('li')
        li['class'] = 'stream_filterlinks'
        a = soup.new_tag('a')
        a['href'] = f'{path}.html'
        a['target'] = '_top'
        a.string = name
        if this_page:
            a['class'] = 'active'
        li.append(a)
        grade_filter.append(li)

    def add_entry_to_gradelist(self, soup: BeautifulSoup, gradelist: Tag, entry: dict, stream_entries: dict):
        entry['grd_grade'] = json.loads(entry['extraAttribs']['grd_grade'])

        div = soup.new_tag('div')
        div['id'] = entry['se_id']
        div['class'] = 'stream_item'
        div['bb:rhs'] = entry['se_rhs']
        path = self.download_local_file(entry['se_rhs'])[1:]
        div['data-path'] = path
        div['onclick'] = 'clickGrade(event);'
        div['aria_controls'] = 'right_stream_mygrades'
        div['role'] = 'tab'
        div['aria_selected'] = 'false'
        div['tabindex'] = '-1'
        grade_value_wrapper = soup.new_tag('div')
        grade_value_wrapper['class'] = 'grade-value-wrapper u_floatThis-left'
        grade_value = soup.new_tag('div')
        grade_value['class'] = 'grade-value'
        grade_value['tabindex'] = '0'
        icon_url = None
        icon_suffix = None
        if 'grade_icon' in entry['grd_grade']:
            grade_icon = entry['grd_grade']['grade_icon']
            if grade_icon == 'completed':
                icon_url = '/images/ci/gradebook/grade_completed_large.png'
                icon_suffix = ' completed'
            elif grade_icon == 'needs_grading':
                icon_url = '/images/ci/gradebook/needs_grading_large.png'
                icon_suffix = ' needs grading'
            elif grade_icon == 'in_progress':
                icon_url = '/images/ci/gradebook/grading_in_progress_large.png'
                icon_suffix = ' in progress'
            elif grade_icon == 'exempt':
                icon_url = '/images/ci/gradebook/exempt_large.png'
                icon_suffix = ' exempt'
        if icon_url:
            icon_path = self.download_local_file(icon_url)
            grade_img = soup.new_tag('img')
            grade_img['src'] = icon_path
            grade_img['class'] = 'largeIcon'
            grade_name = entry['grd_grade']['name'] + icon_suffix
            grade_img['alt'] = grade_name
            grade_img['title'] = grade_name
            grade_img['border'] = '0'
            grade_value.append(grade_img)
        else:
            grade_value.string = entry['grd_grade']['grade']
        grade_value_wrapper.append(grade_value)
        div.append(grade_value_wrapper)
        datestamp = soup.new_tag('span')
        datestamp['class'] = 'stream_datestamp'
        timestamp = entry['se_timestamp']
        if timestamp >= 0:
            datestamp.string = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(timestamp / 1000))
        div.append(datestamp)
        context = soup.new_tag('div')
        context['class'] = 'stream_context'
        context.string = html.unescape(entry['se_context'])
        div.append(context)
        details = soup.new_tag('div')
        details['class'] = 'stream_details'
        details.string = entry['se_details']
        div.append(details)
        context_bottom = soup.new_tag('div')
        context_bottom['class'] = 'stream_context_bottom'

        def find_name_by_id(e: dict):
            course_id = PageCopy.get_entry_course_id(e)
            for course in stream_entries['sv_extras']['sx_courses']:
                if course['id'] == course_id:
                    return course['name']
            return ""

        context_bottom.string = entry['se_bottomContext'].replace('@@X@@AREA@@X@@', '')
        bottom_span = soup.new_tag('span')
        bottom_span['class'] = 'stream_area_name'
        bottom_span.string = find_name_by_id(entry)
        context_bottom.append(bottom_span)
        div.append(context_bottom)
        gradelist.append(div)

    def get_stream_entries(self, stream_name: str):
        payload = {
            'cmd': 'loadStream',
            'streamName': stream_name,
            'providers': {},
            'forOverview': False
        }
        r = self.session.post(f'{base_url}/webapps/streamViewer/streamViewer', data=payload)
        payload['retrieveOnly'] = True
        stream_entries = r.json()
        # Keep retrieving streams at a 1-second interval till the result has been retrieved (similar to blackboard)
        while len(stream_entries['sv_streamEntries']) == 0:
            time.sleep(1)
            r = self.session.post(f'{base_url}/webapps/streamViewer/streamViewer', data=payload)
            stream_entries = r.json()
        return stream_entries

    @staticmethod
    def add_window_height_script(soup: BeautifulSoup, iframe_id: str):
        script = soup.new_tag('script')
        source = '''function getWindowHeight() {
            var winH;
            if ( window.innerHeight ) {
                winH = window.innerHeight;
            } else if ( window.document.documentElement && window.document.documentElement.clientHeight ) {
                winH = window.document.documentElement.clientHeight;
            } else {
                winH = document.body.offsetHeight;
            }
            return winH - globalNavigation.getNavDivHeight();
        }
        '''
        source += f'window.onload = $("{iframe_id}").style.height = getWindowHeight() + "px";'
        script.string = source
        soup.find('body').append(script)

    @staticmethod
    def get_entry_course_id(e: dict):
        try:
            return e['se_courseId']
        except KeyError:
            return e['se_orgId']

    @staticmethod
    def get_entry_timestamp(e: dict):
        return e['se_timestamp']

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
                tree_url = base_url + re.search(r'var treeUrl = "([^"]*)";', script).group(1)
                r = self.session.get(tree_url)
                tree_soup = Utils.soup(string=r.text)
                soup.find('div', id='tree').replace_with(tree_soup)
                message_url = base_url + re.search(r'var messageUrl = "([^"]*)";', script).group(1)
                u, query = self.parse_query(message_url)
                for div in soup.find_all('div', class_='dbThreadMessage'):
                    message_id = re.search(r'message_(.*)', div['id']).group(1)
                    # noinspection PyTypeChecker
                    query['message_id'] = message_id
                    url = self.unparse_query(u, query)
                    r = self.session.get(url)
                    message_soup = Utils.soup(string=r.text)
                    div.clear()
                    div.append(message_soup)
                    del div['style']

    def remove_scripts(self, soup: BeautifulSoup):
        allowed_scripts = ['cdn.js', 'fastinit.js', 'prototype.js', 'actionPanel.js', 'coursemenu.js',
                           'globalNavigation.js', 'lightbox.js', 'page.js', 'tree.js', 'mygrades.js', 'effects.js',
                           'grade_assignment.js', 'inline-grading', 'discussionboard/js', 'stream.js', 'scrollbar.js',
                           'livepipe.js', 'slider.js']
        not_allowed_keywords = ['streamName']
        allowed_keywords = ['page.bundle.addKey', 'PageMenuToggler', 'PaletteController', 'mygrades', 'gradeAssignment',
                            'collapsiblelist', 'postInit', 'var courseId']
        for script in soup.find_all('script'):
            if script.has_attr('src'):
                # Keep allowed scripts
                if not any(name in script['src'] for name in allowed_scripts):
                    script.decompose()
            else:
                def contains_keyword(text, keywords):
                    return any(keyword in text for keyword in keywords)

                # Always decompose scripts containing not allowed keywords even if they also contain allowed keywords
                if contains_keyword(script.text, not_allowed_keywords):
                    script.decompose()
                # Keep lines containing allowed keywords
                elif contains_keyword(script.text, allowed_keywords):
                    lines = script.text.split('\n')
                    allowed_lines = [self.rewrite_line(line) for line in lines if
                                     contains_keyword(line, allowed_keywords)]
                    new_script = '\n'.join(allowed_lines)
                    script.string.replace_with(new_script)
                else:
                    script.decompose()
        # Add fake DWR to prevent errors
        self.add_fake_dwr(soup)
        # Init streams if needed
        self.add_streams_init(soup)

    def rewrite_line(self, line: str):
        line = line.strip()
        # Special case for grade assignments
        if 'gradeAssignment.init' in line:
            def url_replace(match):
                url = match.group(2)
                path = self.download_local_file(url)[1:]
                return match.group(1) + path + match.group(3)

            line = re.sub(r'("downloadUrl":")(.*?)(",)', url_replace, line)
        return line

    @staticmethod
    def add_fake_dwr(soup: BeautifulSoup):
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
    def add_streams_init(soup: BeautifulSoup):
        if soup.find('script', src=re.compile(r'stream\.js')):
            script = soup.new_tag('script')
            script.string = 'window.addEventListener("load", function() { window.stream.fitScrollableRegionToBrowser(); }, false); '
            soup.find('body').append(script)

    @staticmethod
    def cleanup_page(soup: BeautifulSoup):
        def decompose(name=None, **kwargs):
            for tag in soup.find_all(name, **kwargs):
                tag.decompose()

        decompose(class_='hideFromQuickLinks')  # Quick Links
        decompose(class_='edit_controls')  # Edit settings
        decompose(class_='contextMenuContainer')  # Context menu
        decompose(id='quickLinksLightboxDiv')  # Quick links
        decompose(id='quick_links_wrap')  # Quick links
        decompose(class_='global-nav-bar-wrap')  # User menu
        decompose(id='breadcrumb_controls_id')  # Navigation helper
        decompose(class_='courseArrow')  # Courses menu
        decompose(class_='actionBarMicro')  # Courses menu
        decompose(class_='localViewToggle')  # Courses menu
        decompose(id='controlPanelPalette')  # Course management panel
        decompose(class_='eudModule')  # Home page modules
        decompose(id='actionbar')  # Action bar
        decompose(class_='subActionBar')  # Action bar
        decompose(class_='dbThreadFooter')  # Thread footer
        decompose(id='copyright')  # Copyright at page bottom
        decompose(class_='taskbuttondiv_wrapper')  # Task submission buttons
        decompose(id='step2')  # Assignment submission
        decompose(id='step3')  # Add comments
        decompose(class_='submitStepBottom')  # Assignment submission buttons
        decompose(id='iconLegendLinkDiv')  # Icon legend
        decompose(class_='containerOptions')  # Action bar options
        decompose(id=re.compile(r'showAllButton', re.IGNORECASE))  # Discussion Board show all
        decompose(id=re.compile(r'openpaging', re.IGNORECASE))  # Discussion Board edit
        decompose(id=re.compile(r'editpaging', re.IGNORECASE))  # Discussion Board edit
        decompose(id=re.compile(r'collectAction', re.IGNORECASE))  # Discussion Board Collect
        decompose(id=re.compile(r'removeListAction', re.IGNORECASE))  # Discussion Board Remove
        decompose(id=re.compile(r'reorderControls', re.IGNORECASE))  # Reordering
        decompose(id='top_list_action_bar')  # Discussion Board action bar
        decompose(id='bottom_list_action_bar')  # Discussion Board action bar
        decompose(class_='renameCourseToc')  # Rename menu
        decompose(class_='quickAddPal')  # Adding items to course
        decompose(class_='reorder')  # Course menu reordering
        decompose(class_='receiptDate')  # Date of error
        decompose(class_='secondaryControl')  # Refresh buttons
        decompose('h2', class_='navDivider', text=re.compile(r'Course Management'))  # Course management
        decompose('li', class_='sub')  # Thread actions
        decompose(onclick=re.compile(r'contentList\.toggleDetails'))  # Contentlist edit toggle
        decompose(id='threadArea')  # Thread navigation
        decompose(class_='backLink')  # Remove backlinks to avoid duplicates
        decompose(class_='captionText')  # Error IDs
        decompose(id='side_nav')  # Grades side menu
        decompose(class_='announcementFilter')  # Announcement filter menu
        decompose(onclick=re.compile(r'bb-social-learning-bb_bb60'))  # Grade overview filters
        decompose('div', class_='streamError')  # Grade overview loading box

        def unwrap(name=None, **kwargs):
            for tag in soup.find_all(name, **kwargs):
                tag.unwrap()

        unwrap('input', type='hidden')

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
        decompose_url('tool_id=_118_1')  # Groups
        decompose_url('displayEmail')  # Email
        decompose_url('viewExtendedHelp')  # Help pages
        decompose_url('launchAssessment')  # Assessments
        decompose_url('groupContentList')  # Groups
        decompose_url('groupInventoryList')  # Group management

        def delete_attribute(attribute, name=None, **kwargs):
            for tag in soup.find_all(name, **kwargs):
                del tag[attribute]

        delete_attribute('href', 'a', class_='sortheader')  # Column sorting

        def delete_url(url_part):
            for a in soup.find_all('a', {'href': True}):
                if url_part in a['href']:
                    del a['href']

        delete_url('oslt-signUpList-bb_bb60')  # Sign up lists
        delete_url('eph-ephorus-assignment-bb_bb60')  # Ephorus assignments

        def replace_class(old_class, new_classes=None):
            for tag in soup.find_all(class_=old_class):
                tag['class'].remove(old_class)
                if new_classes:
                    tag['class'].extend(new_classes)
                if not tag['class']:
                    del tag['class']

        replace_class('ineditmode')  # Edit mode markup
        replace_class('contentBox-edit')  # Edit mode markup
        replace_class('reorderableModule')  # Edit mode markup
        replace_class('reorderable')  # Edit mode markup
        replace_class('dragHandle')  # Edit mode markup
        replace_class('dndHandle')  # Edit mode markup
        replace_class('buildList', ['announcementList', 'announcementList-read'])  # Announcements edit mode
        replace_class('liItem', ['read'])  # Contentlist edit mode
        replace_class('ok')  # Avoids duplicates

    @staticmethod
    def replace_navbar(soup: BeautifulSoup):
        if soup.find('div', id='globalNavPageNavArea'):
            soup.find('td', id='My Blackboard').decompose()
            soup.find('td', id='Courses.label').find('a')['href'] = 'Courses.html'
            soup.find('td', id='Organisations').find('a')['href'] = 'Organisations.html'
            grades = soup.find('td', id='Support')
            grades.find('a')['href'] = 'Grades.html'
            grades.find('span').string.replace_with('Grades')

    def replace_onclick(self, soup: BeautifulSoup):
        for a in soup.find_all('a', {'onclick': True}):
            if 'loadContentFrame' in a['onclick']:
                href = re.search(r"loadContentFrame\('(.*)'\)", a['onclick']).group(1)
                path = self.download_local_file(href)[1:]
                a['href'] = path
                a['target'] = '_top'
                del a['onclick']
            elif 'gradeAssignment.inlineView' in a['onclick']:
                course_id_script = soup.find('script', text=re.compile(r'var *courseId')).text
                course_id = re.search(r"var *courseId *= *'(.*?)'", course_id_script).group(1)
                r = re.search(r"gradeAssignment\.inlineView(?:GroupFile)?\(.*?, *'(.*?)', *'(.*?)' *\)", a['onclick'])
                file_id = r.group(1)
                attempt_id = r.group(2)
                url = f'/webapps/assignment/inlineView?course_id={course_id}&file_id={file_id}&attempt_id={attempt_id}'
                if 'gradeAssignment.inlineViewGroupFile' in a['onclick']:
                    url += '&group=true'
                json = self.session.get(base_url + url).text
                # TODO: Selected does not work
                a['onclick'] = f'gradeAssignment.handleInlineViewResponse({json});'

    def replace_local_urls(self, soup: BeautifulSoup, tag: str, attr: str, url_dir: str):
        for element in soup.find_all(tag, {attr: True}):
            url = self.strip_base_url(element[attr].strip())
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

    def download_local_file(self, full_url: str):
        url, fragment = self.split_url(full_url)
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
            url, fragment = self.split_url(r.url)

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
                    local_path, exists = self.generate_page_title(Utils.soup(string=r.text))
                    if exists:
                        if Config.DEBUG:
                            print(f'Duplicate : {local_path}')
                        self.update_url_dict(local_path, url=url, request=r)
                        return local_path
                    full_path = self.get_full_path(local_path)

            print(f'Retrieving: {local_path}')
            self.update_url_dict(local_path, url=url, request=r)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # HTML pages need te be processed
            if is_html:
                if Config.DEBUG:
                    debug_path = self.get_full_path('/debug' + local_path)[:-5] + '.link'
                    os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                    urls = {'old_url': base_url + self.strip_base_url(full_url), 'new_url': base_url + url}
                    Utils.write(debug_path, urls)
                navigation_tag = soup.find('div', class_='path', role='navigation')
                if navigation_tag:
                    # Remove illegal path chars
                    navigation_strings = map(lambda s: re.sub(r'[<>:"/\\|?*.]', '', s), navigation_tag.stripped_strings)
                    self.navigation_stack.append('/'.join(navigation_strings))
                url_dir = posixpath.dirname(url)
                self.process_page(soup, url_dir)
                if navigation_tag:
                    self.navigation_stack.pop()
                Utils.write(full_path, soup.prettify())
            # CSS urls need to be rewritten
            elif os.path.splitext(full_path)[1] == '.css':
                url_dir = posixpath.dirname(url)
                local_dir = posixpath.dirname(local_path)
                css = self.replace_css_urls(r.text, url_dir, local_dir)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(css)
            # Other files can be stored without processing
            else:
                with open(full_path, 'wb') as f:
                    # Use chunks in case of very large files
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            return local_path + fragment

    def generate_page_title(self, soup: BeautifulSoup):
        comment_tag = soup.contents[1]
        edit_mode = isinstance(comment_tag, Comment) and 'listContentEditable.jsp' in str(comment_tag)

        navigation_tag = soup.find('div', class_='path', role='navigation')
        if navigation_tag:
            title = ' - '.join(navigation_tag.stripped_strings)
        else:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text
            else:
                title = 'unknown'
        if edit_mode:
            title += ' (edit mode)'
        # Remove illegal filename characters
        title = re.sub(r'[<>:"/\\|?*]', '', title)

        self.remove_scripts(soup)
        self.cleanup_page(soup)
        soup = soup.prettify()

        local_path = None
        max_length = 255
        exists = False
        done = False
        counter = 0
        while not done:
            local_path = f'/{title}.html' if counter == 0 else f'/{title} ({counter}).html'
            if len(local_path) > max_length:
                # Truncate title if too long
                title = title[:max_length - len(local_path)]
            elif local_path in self.downloaded_pages:
                if soup == self.downloaded_pages[local_path]:
                    exists = True
                    done = True
                else:
                    counter += 1
            else:
                self.downloaded_pages[local_path] = soup
                done = True
        if Config.DEBUG:
            debug_path = self.get_full_path('/debug' + local_path)
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            Utils.write(debug_path, soup)
        return local_path, exists

    def replace_css_urls(self, css: str, url_dir: str, local_dir: str = '/'):
        def url_replace(match):
            url = match.group(2).strip()
            url = self.strip_base_url(url)
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
                redirected_url = self.split_url(redirect.url)[0]
                self.url_dict[redirected_url] = path

    @staticmethod
    def get_full_path(local_path: str):
        if local_path.startswith('/../'):
            return Config.DOWNLOAD_PATH + local_path[4:]
        else:
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
    def get_url_dir(url: str):
        return posixpath.dirname(PageCopy.strip_base_url(url))

    @staticmethod
    def strip_base_url(url: str):
        if url.startswith(base_url):
            url = url[len(base_url):]
        return url

    @staticmethod
    def split_url(url: str):
        url = PageCopy.strip_base_url(url)
        fragment = ''
        fragment_index = url.find('#')
        if fragment_index > 0:
            url, fragment = url[:fragment_index], url[fragment_index:]
        if '?' in url:
            url = PageCopy.sanitize_url_params(url)
        return url, fragment

    @staticmethod
    def sanitize_url_params(url: str):
        u, query = PageCopy.parse_query(url)
        if 'toggle_mode' in query:
            del query['toggle_mode']

        if 'mode' in query and query['mode'][0] in ['reset', 'view', 'cpview']:
            del query['mode']

        if 'nav' in query and 'discussion_board_entry' in query['nav']:
            query['nav'].remove('discussion_board_entry')
            query['nav'].append('discussion_board')

        return PageCopy.unparse_query(u, query)

    def url_to_path(self, url: str):
        if '/webapps/assignment/download' in url:
            attempt_id = re.search(r'attempt_id=_(.*?)_1', url).group(1)
            filename = re.search(r'fileName=([^&]*)', url).group(1)
            path = f'/../{self.navigation_stack[-1]}/{attempt_id} - {filename}'
        else:
            if '#' in url:
                url = url[:url.find('#')]
            if '?' in url:
                url = url[:url.find('?')]
            if 'bbcswebdav' in url and 'dt-content-rid' in url:
                filename = posixpath.basename(url)
                path = f'/../{self.navigation_stack[-1]}/{filename}'
            else:
                path = url
        path = urllib.parse.unquote(path)
        return path

    @staticmethod
    def parse_query(url: str):
        u = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(u.query)
        return u, query

    @staticmethod
    def unparse_query(u, query):
        # noinspection PyProtectedMember,PyTypeChecker
        u = u._replace(query=urllib.parse.urlencode(sorted(query.items()), True, quote_via=urllib.parse.quote))
        url = urllib.parse.urlunparse(u)
        return url
