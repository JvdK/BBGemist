import json
import logging
import os
from getpass import getpass
from urllib.parse import unquote

import requests

import Config
import Request
import Utils
from Downloader import Downloader


class Download(Downloader):
    username = None
    password = None
    base_url = "https://blackboard.utwente.nl"

    def __init__(self):
        logging.debug("--- Initialising Downloader ---")

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

        if self.login():
            print("Logged in!")
        else:
            print("ERROR logging in...")

        Utils.clear()

        course_url = input("Enter course link:\n")
        print()
        course_info = self.get_course_info(course_url)
        print()

        logging.debug(json.dumps(course_info, indent=4))

        input("Press [Enter] to start downloading the pages...")
        print()

        course_pages = self.get_course_pages(course_info)

        for course_page in course_pages:
            self.parse_course_page(course_info, course_page)

        print("Done!")

    def login(self):
        r = self.session.get('https://blackboard.utwente.nl/webapps/portal/execute/defaultTab')
        soup = Utils.soup(string=r.text)
        value = soup.find('input', attrs={'name': 'blackboard.platform.security.NonceUtil.nonce'})['value']
        login_url = f'{self.base_url}/webapps/login/'
        payload = {
            'user_id': self.username,
            'password': self.password,
            'login': 'Login',
            'action': 'login',
            'new_loc': '',
            'blackboard.platform.security.NonceUtil.nonce': value
        }
        r = self.session.post(login_url, data=payload)
        return 'webapps/portal/execute/tabs' in r.text

    def get_course_info(self, course_url):
        print("Getting Course Information...")
        print()

        logging.info("Course URL: {}".format(course_url))

        logging.debug("Fetching course URL...")

        self.headers["Referer"] = "https://blackboard.utwente.nl/"
        self.headers["Host"] = "blackboard.utwente.nl"

        r = self.session.get(course_url, headers=self.headers, allow_redirects=True)

        logging.debug("Fetched course URL")

        logging.debug("Souping HTML...")
        soup = Utils.soup(string=r.content)
        logging.debug("Souped HTML")

        course_name = soup.select("#courseMenu_link")
        if len(course_name) > 0:
            course_name = course_name[0].text
        else:
            logging.critical("Course name HTML element 'courseMenu_link' not found")
            exit()

        course_name = course_name.replace("/", "&").replace("\\", "&")

        logging.info("Course Name: {}".format(course_name))

        print("Course name:")
        print(course_name)
        print()

        course_id = course_url.split("&id=")[-1].split("&")[0]

        print("Course id:")
        print(course_id)
        print()

        Utils.create_folder_if_not_exists(Config.CACHE_PATH + course_name)
        Utils.write(Config.CACHE_PATH + course_name + "\\index.html", str(soup))

        print("Course folders:")
        folders = []

        course_folders = soup.select("#courseMenuPalette_contents")[0].find_all("a")
        for course_folder in course_folders:
            course_folder_url = course_folder.get("href")
            course_folder_name = course_folder.find_all("span")[0].text.strip()

            print("- {}".format(course_folder_name))

            skip = [
                "Course Home Page",
                "tool_id=_115", # email
                "tool_id=_119", # discussion board
                "tool_id=_167", # contacts
                "tool_id=_178" # grades added manually
            ]

            if not any(x in course_folder_url for x in skip) and not any(x in course_folder_name for x in skip):
                folders.append({
                    "folder": course_folder_name,
                    "url": course_folder_url
                })

        print()

        folders.append({
            "folder": "My Grades",
            "url": "/webapps/bb-mygrades-bb_bb60/myGrades?course_id={}&stream_name=mygrades&is_stream=false".format(course_id)
        })

        return {
            "course_url": course_url,
            "course_name": course_name,
            "course_folders": folders
        }

    def get_course_pages(self, course_info: dict):
        if "course_folders" not in course_info.keys():
            logging.critical("Course folders missing in dict!")
            exit()
        elif len(course_info["course_folders"]) == 0:
            logging.critical("Course folders empty!")
            exit()

        course_pages = []
        for course_folder in course_info["course_folders"]:
            logging.info("Getting Course Page...")
            logging.info("Course Content Page: {}".format(course_folder["folder"]))
            logging.info("Course Content URL : {}".format(course_folder["url"]))
            logging.info("Course Name        : {}".format(course_info["course_name"]))

            course_page_path = course_info["course_name"] + "/" + course_folder["folder"]
            course_page_html = course_info["course_name"] + "/" + course_folder["folder"] + ".html"
            logging.info("Course Content Path: {}".format(course_page_path))
            logging.info("Course Content HTML: {}".format(course_page_html))

            # Save course content page to cache
            print("Downloading Page: {}".format(course_page_path))
            r = self.session.get("https://blackboard.utwente.nl" + course_folder["url"])

            Utils.create_file_if_not_exists(Config.CACHE_PATH + course_page_html)
            Utils.write(Config.CACHE_PATH + course_page_html, r.text)

            Utils.wait(seconds=5, variable=3, countdown=True)

            course_pages.append(Config.CACHE_PATH + course_page_html)

        return course_pages

    def parse_course_page(self, course_info, course_page):
        if "Announcements" in course_page:
            pass

        elif "Grades" in course_page:
            self.parse_grades(course_page, course_info["course_name"])

        else:
            soup = Utils.soup(file=course_page)

            folder_path = []
            path = soup.select("#breadcrumbs")[0].select(".path")[0].find_all("li")[1:]
            for path_item in path:
                if path_item.text.strip() != "":
                    folder_path.append(path_item.text.strip())
                    print(path_item.text.strip())
                    logging.debug(path_item.text.strip())

            folder = course_info["course_name"] + "/" + "/".join(folder_path) + "/"

            print()

            if len(soup.select("#content_listContainer")) == 0:
                input("There is no content on this page?")

                return

            sections = soup.select("#content_listContainer")[0].select(".read")
            print("Number of sections: {}".format(len(sections)))
            for section in sections:
                print("Section Title: {}".format(section.find("h3").text.strip()))

                # Determine Section Type
                image = section.find("img")
                if len(image) > 0:
                    if image.get("alt") is not None:
                        section_type = image.get("alt")  # No other way to get type... Bad bad Blackboard...

                        if section_type == "Content Folder":
                            input("A sub-folder was found! Press [Enter] to download this folder...")

                            folder_url = "https://blackboard.utwente.nl" + section.find("h3").find("a").get("href")
                            folder_name = section.find("h3").text.strip().replace("/", "&").replace("\\", "&")

                            print("Folder URL: {}".format(folder_url))
                            print("Folder Name: {}".format(folder_name))

                            r = self.session.get(folder_url)

                            Utils.create_file_if_not_exists(Config.CACHE_PATH + folder + folder_name + ".html")
                            Utils.write(Config.CACHE_PATH + folder + folder_name + ".html", r.text)

                            self.parse_course_page(course_info, Config.CACHE_PATH + folder + folder_name + ".html")

                        elif section_type == "Assignment":
                            input("An assignment was found! Press [Enter] to download this assignment...")

                            assignment_url = "https://blackboard.utwente.nl" + section.find("h3").find("a").get("href")
                            assignment_name = section.find("h3").text.strip().replace("/", "&").replace("\\", "&")

                            file_name = course_info["course_name"] + "\\[Assignments]\\" + assignment_name + ".html"
                            file_name = Config.CACHE_PATH + "".join(i for i in file_name if i not in ':*?"<>|')

                            print("Writing submission info page: {}".format(file_name))
                            r = self.session.get(assignment_url)

                            Utils.create_file_if_not_exists(file_name)
                            Utils.write(file_name, r.text)

                            self.parse_submission(file_name, course_info["course_name"], assignment_name)

                        else:


                            print("Something else...")


                    else:
                        logging.error("No alt text for image")
                else:
                    logging.critical("Could not determine section type")

                # Get Files for Section
                attachments = section.select(".attachments")
                if len(attachments) > 0:
                    attachments_files = attachments[0].find_all("li")
                    if len(attachments_files) > 0:
                        if len(attachments_files) > 2:
                            print("Discovered {} files".format(len(attachments_files) / 2))
                        else:
                            print("Discovered {} file".format(len(attachments_files) / 2))

                        for attachments_file in attachments_files:
                            file_url = "https://blackboard.utwente.nl" + attachments_file.find("a").get("href")
                            file_name = attachments_file.find("a").text.strip()
                            if file_name == "":
                                continue
                            if len(file_name.split(".")) == 1:
                                file_name = file_name + " - " + unquote(attachments_file.find("span").get("bb:menugeneratorurl").split("/")[6].split("?")[0])
                            file_size = attachments_file.find("span").text.strip()

                            self.files.append({
                                "folder": folder,
                                "file_url": file_url,
                                "file_name": file_name,
                                "file_size": file_size,
                            })

                            print("- " + attachments_file.find("a").text.strip())
                            logging.info("File URL: {}".format(file_url))
                            logging.info("File Name: {}".format(file_name))
                            logging.info("File Size: {}".format(file_size))

                            print("\nPress enter to download")
                            input()

                            print("Downloading File...")
                            Utils.info("Course", course_info["course_name"])
                            Utils.info("Folder", folder.replace(course_info["course_name"], ""))
                            download = self.download_file(url=file_url,
                                                          folder=folder,
                                                          file_name=file_name)

                print()

    def download_file(self, url, folder, file_name):
        download = Request.download(downloader=self,
                                    url=url,
                                    folder=folder,
                                    file_name=file_name,
                                    checksum=Config.CHECKSUM_FILE)

        return download

    def parse_grades(self, grades_file, folder):
        print("Parsing Grades")
        soup = Utils.soup(grades_file)

        submissions = soup.find_all("div", {"class": "row"})

        for submission in submissions:
            if len(submission.find_all("a")) > 0 and "uploadAssignment?action=showHistory" in submission.find_all("a")[0].get("onclick"):
                url = self.base_url + submission.find("a").get("onclick").split("('")[1].split("')")[0]
                name = submission.find("a").text

                file_name = folder + "\\[Assignments]\\" + name + ".html"
                file_name = Config.CACHE_PATH + "".join(i for i in file_name if i not in ':*?"<>|')

                print("Writing submission info page: {}".format(file_name))
                r = self.session.get(url)

                if os.path.isfile(file_name):
                    print("Submission already downloaded!")
                else:
                    Utils.create_file_if_not_exists(file_name)
                    Utils.write(file_name, r.text)

                    self.parse_submission(file_name, folder, name)

                Utils.wait(3)

    def parse_submission(self, submission_page, folder, name):
        print("Parsing Submission")
        soup = Utils.soup(submission_page)

        if "Browse Local Files. Opens the File Upload window to upload files from your computer." in str(soup):
            print("This is a submission page! Deleting html!")
            os.remove(submission_page)

            return

        assignment_files = soup.find("div", {"id": "assignmentInfo"})
        assignment_files = assignment_files.find("ul")
        if assignment_files is not None:
            print("Found {} assignment files".format(len(assignment_files.find_all("a"))))

            assignment_files = assignment_files.find_all("a")

            input("Press [Enter] to download assignment files...")

            for assignment_file in assignment_files:
                filename = unquote(assignment_file.text)
                url = assignment_file.get("href")

                download = self.download_file(url=self.base_url + url,
                                              folder=folder + "/[Assignments]/" + name + "/",
                                              file_name="[Assignment] " + filename)

                Utils.wait(3)

        submission_files = soup.find_all("a", {"class": "dwnldBtn"})

        print("Found {} submitted files".format(len(submission_files)))
        print()
        input("Press [Enter] to download submission files...")

        for submission_file in submission_files:
            filename = unquote(submission_file.get("href").split("=")[-1])
            url = submission_file.get("href")

            download = self.download_file(url=self.base_url + url,
                                          folder=folder + "/[Assignments]/" + name + "/",
                                          file_name=filename)

            Utils.wait(3)
