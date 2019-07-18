import codecs
import datetime
import hashlib
import json

import os
import random

import time

import math

import re
from distutils.util import strtobool

from bs4 import BeautifulSoup

import Config


def delete(file: str):
    os.remove(file)


def write(file: str, dump):
    if isinstance(dump, str):
        # print("This is a string")
        pass
    elif isinstance(dump, dict):
        # print("This is a dict, using JSON encoder")
        dump = json.dumps(dump, indent=4)
    elif isinstance(dump, list):
        # print("This is a list, using JSON encode")
        dump = json.dumps(dump)
    else:
        print("Unsupported type")
        input()

    # print(dump)

    with codecs.open(file, mode="w", encoding="utf-8") as f:
        f.write(dump)


# TODO: Allow json
def add(file: str, line):
    create_file_if_not_exists(file)

    with codecs.open(file, mode="a", encoding="utf-8") as f:
        f.write(line + "\r\n")


# TODO: decide what / \ to use for folder separation
def add_hash(checksum_file: object, file: object):
    """
    Adds the hash of a file to a specified hash file.
    :param checksum_file:
    :param file:
    """
    file_hash = get_hash(file)

    add(checksum_file, "{} *{}".format(file_hash, file.replace("/", "\\")))


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def date(short: bool = False):
    if short:
        return time.strftime("%Y%m%d")
    else:
        return time.strftime("%Y-%m-%d %H:%M:%S")


def info(name: str, string: str):
    string = str(string)

    if len(name) > 7:
        input("Value name for info() too long!")

    if len(string) > 80:
        string = "%s...%s" % (string[:40], string[-40:])

    if re.search("(.?\r)", string):
        print("{:7} : {}".format(name, string), end="")
    else:
        print("{:7} : {}".format(name, string))


def create_file_if_not_exists(file: str):
    if not os.path.isfile(file):
        # logging.info("Creating file {}".format(file))
        create_folder_if_not_exists(os.path.dirname(file))
        create_file = open(file, 'wb')
        create_file.close()
        # logging.info("Created file {}".format(file))
    else:
        # logging.info("File {} already exists".format(file))
        pass


def create_folder_if_not_exists(path: str):
    if not os.path.isdir(path):
        # logging.info("Creating folder {}".format(path))
        os.makedirs(path, exist_ok=True)
        # logging.info("Created folder {}".format(path))
    else:
        # logging.info("Folder {} already exists".format(path))
        pass


def soup(file: str = None, string: str = None, errors=None):
    if file and string:
        raise NotImplementedError
    elif file:
        # print("Loading HTML: {}".format(file))
        if os.path.isfile(file):
            if errors is not None:
                html = BeautifulSoup(codecs.open(file, mode="r", encoding="utf-8", errors=errors), "html.parser")
            else:
                html = BeautifulSoup(codecs.open(file, mode="r", encoding="utf-8"), "html.parser")
        else:
            raise FileNotFoundError("HTML file not found!")
    elif string:
        # print("Parsing HTML...")
        html = BeautifulSoup(string, "html.parser")
    else:
        raise NotImplementedError

    return html


def data(file: str = None, string: str = None):
    if file and string:
        raise NotImplementedError
    elif file:
        if os.path.isfile(file):
            file = json.load(codecs.open(file, mode="r", encoding="utf-8"))
        else:
            raise FileNotFoundError("JSON file not found!")
    elif string:
        file = json.loads(string, encoding="utf-8")
    else:
        raise NotImplementedError

    return file


def load(method, file: str, limit: int = math.inf, contains: str = None) -> []:
    archive = []
    index = 0

    print("Loading : {}".format(file.split("/")[-1]))

    with codecs.open(file, mode="r", encoding="utf-8") as f:
        for line in f.readlines():
            print("Parsing : {}...\r".format(index), end="")

            line = line.strip()

            if line:
                if contains:
                    if contains in line:
                        archive.append(method(line))
                    else:
                        continue
                else:
                    archive.append(method(line))

            index += 1

            if index > limit:
                break

    if index == 0:
        print("Parsing : 0...\r", end="")
    else:
        print("Parsing : {}...\r".format(index), end="")

    print()
    print()

    return archive


def page(lines):
    clear()
    for line in lines:
        print(line)

    lines_empty = Config.CONSOLE_HEIGHT - len(lines)

    for i in range(0, lines_empty):
        print("")


def wait(seconds: int = 10, variable: int = 0, do: bool = True, message: str = None, countdown: bool = False):
    time_to_wait = int(seconds + random.random() * variable)

    resume_time = time_to_wait + int(time.time())
    resume_time = datetime.datetime.fromtimestamp(resume_time).strftime("%H:%M:%S")

    if message and countdown:
        while time_to_wait > 0:
            info("Next", "{} at {} in {} seconds...    \r".format(message, resume_time, time_to_wait))

            time.sleep(1)

            time_to_wait -= 1

        info("Next", "{} at {}                           ".format(message, resume_time, time_to_wait))
    elif message:
        info("Next", "{} at {}".format(message, resume_time))
    elif countdown:
        while time_to_wait > 0:
            print("Continuing in {} seconds...\r".format(time_to_wait), end="")

            time.sleep(1)

            time_to_wait -= 1

        print(32*" ")
    if do:
        time.sleep(time_to_wait)
    else:
        return time_to_wait


def files(path: str, contains: [str] = None, base_path: str = None) -> []:
    # check folder exists
    if not os.path.isdir(path):
        return []

    # get all files from path
    file_names = [file for file in os.listdir(path) if os.path.isfile(os.path.join(path, file))]

    # filter files when given
    if contains:
        if type(contains) == list:
            file_names = [file for file in file_names if all(string in file for string in contains)]
        elif type(contains) == str:
            file_names = [file for file in file_names if contains in file]
        else:
            raise NotImplementedError

    # add base path when given
    if base_path:
        file_names = [base_path + file for file in file_names]

    return file_names


def file(path: str, contains: [str] = None, base_path: str = None) -> "":
    file_list = files(path=path, contains=contains, base_path=base_path)

    if isinstance(file_list, list):
        return file_list[0]
    elif isinstance(file_list, str):
        return file_list
    else:
        return ""


def progress(current, total, percentage=False, length: int = 20):
    if percentage:
        return "[" + (math.ceil((current / total) * length) * "=") + (
                    (length - math.ceil((current / total) * length)) * " ") + "] " + "{:6.2f}%".format(
            (current / total) * 100)
    else:
        return "[" + (math.ceil((current / total) * length) * "=") + (
                    (length - math.ceil((current / total) * length)) * " ") + "]"


def between(string: str, start: str, end: str) -> str:
    """
    Returns the sub-string between the specified start and end parameters.
    :param string: The string where the sub-string should be extracted from.
    :param start: The part before the sub-string.
    :param end: The part after the sub-string.
    :return: The extracted sub-string.
    """
    result = re.search(re.escape(start) + '(.*)' + re.escape(end), string).group(1)

    return result


def get_hash(file_name):
    buffer_size = 65536

    sha256 = hashlib.sha256()

    with open(file_name, 'rb') as f:
        while True:
            file_data = f.read(buffer_size)
            if not file_data:
                break
            sha256.update(file_data)

    return sha256.hexdigest()


def show(dump: dict):
    """
    Prints a JSON or dict object.
    :param dump: The JSON of dict object.
    """
    print(json.dumps(dump, indent=4))


def yes_or_no(question):
    """
    Aks the user a yes or no question and returns the result.
    :param question: The question that should be asked.
    :return: True for yes, False for no,
    """

    user_input = input(f"{question} [y/n]\n> ")
    result = None
    while result is None:
        try:
            result = strtobool(user_input)
        except ValueError:
            user_input = input("Please answer with y/n\n> ")
    return result
