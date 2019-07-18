import json
import logging
import os
from getpass import getpass

import requests

import Config
import Request
import Utils
from Downloader import Downloader


class Download(Downloader):
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

        Utils.wait(3)

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
        login_url = "https://blackboard.utwente.nl/webapps/login/"

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
                "tool_id=_115",
                "tool_id=_119",
                "tool_id=_167"
            ]

            if not any(x in course_folder_url for x in skip) and not any(x in course_folder_name for x in skip):
                folders.append({
                    "folder": course_folder_name,
                    "url": course_folder_url
                })

        print()

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

            ###
            # break
            ###

        return course_pages

    def parse_course_page(self, course_info, course_page):
        if "Announcements" in course_page:
            print("Sorry, saving announcements feature will be implemented later!")
            print()

        elif "Grades" in course_page:
            print("Sorry, saving submissions feature will be implemented later!")
            print()

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
                            input("A subfolder was found! Press [Enter] to download this folder...")

                            folder_url = "https://blackboard.utwente.nl" + section.find("h3").find("a").get("href")
                            folder_name = section.find("h3").text.strip().replace("/", "&").replace("\\", "&")

                            print("Folder URL: {}".format(folder_url))
                            print("Folder Name: {}".format(folder_name))

                            r = self.session.get(folder_url)

                            Utils.create_file_if_not_exists(Config.CACHE_PATH + folder + folder_name + ".html")
                            Utils.write(Config.CACHE_PATH + folder + folder_name + ".html", r.text)

                            self.parse_course_page(course_info, Config.CACHE_PATH + folder + folder_name + ".html")
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
                        if len(attachments_files) > 1:
                            print("Discovered {} files".format(len(attachments_files)))
                        else:
                            print("Discovered {} file".format(len(attachments_files)))

                        for attachments_file in attachments_files:
                            file_url = "https://blackboard.utwente.nl" + attachments_file.find("a").get("href")
                            file_name = attachments_file.find("a").text.strip()
                            file_size = attachments_file.find("span").text.strip()

                            self.files.append({
                                "folder": folder,
                                "file_url": file_url,
                                "file_name": file_name,
                                "file_size": file_size,
                            })

                            print("- " + attachments_file.text.strip())
                            logging.info("File URL: {}".format(file_url))
                            logging.info("File Name: {}".format(file_name))
                            logging.info("File Size: {}".format(file_size))

                            print("Press enter to download")
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

        # log to archive to resume downloads

        return download
