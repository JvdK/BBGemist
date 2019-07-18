import logging

import Actions
import Config
import Utils
from PageCopy import PageCopy


def main():
    lines = [
        "BBGemist",
        "========",
        "",
        "BBGemist downloads all course data from a Blackboard course, including files, submissions, announcements and ",
        "information available on pages.",
        "",
        "Because Blackboard requires you to login to view courses. You need to enter your username and password. This ",
        "program does not store or keep your login credentials.",
        "",
        "After entering your username and password, it will ask for a link to a course. Copy a link to a course from ",
        "your My Blackboard or Courses page.",
        "",
        "Please do not share or publish the generated files as it contains personal information.",
        "",
        "- Copyright 2019, JvdK - Disclaimer: USE AT YOUR OWN RISK!",
        "",
        "",
        "Enter a number below to acknowledge the above statements and start downloading."
    ]

    for action in Actions.actions:
        lines.append("{:{width}} : {}".format(action.code, action.name, width=Actions.width))

    Utils.page(lines)

    command = input("> ")

    Utils.clear()

    if command in Actions.codes:
        for action in Actions.actions:
            if action.code == command:
                action.action()
    else:
        lines = ["No action with code: {}".format(command)]

        Utils.page(lines)


Utils.create_folder_if_not_exists(Config.CACHE_PATH)
Utils.create_file_if_not_exists(Config.LOG_FILE)

logging.basicConfig(filename=Config.LOG_FILE,
                    level=logging.DEBUG,
                    format='%(asctime)s %(name)-22s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

logging.info("======================")
logging.info("=== Start BBGemist ===")
logging.info("======================")

logging.info('Start logging...')

# FIXME: Debug only
# main()
PageCopy()

logging.info('Exiting application...')