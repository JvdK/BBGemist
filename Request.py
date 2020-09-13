import os
import random

import time

import Config
import Utils

total_downloaded = 0


def download(downloader, url, folder, file_name=None, referrer=None, cookie=None, checksum=None):
    global total_downloaded
    total_downloaded_mb = 0

    # set headers #
    headers = {"User-Agent": Config.USER_AGENT}
    if cookie:
        Utils.info("Cookie", cookie)
        headers["Cookie"] = cookie
    if referrer:
        Utils.info("Refer", referrer)
        headers["Referer"] = referrer

    # print info #
    Utils.info("URL", url)

    # filename #
    if file_name is None:
        file_name = url.split("/")[-1]
    file_name = "".join(i for i in file_name if i not in '\/:*?"<>|')

    # folder #
    folder = Config.DOWNLOAD_PATH + "".join(i for i in folder if i not in ':*?"<>|')

    # make folders #
    Utils.create_folder_if_not_exists(folder)

    # add random string to file name if it already exists #
    if os.path.isfile(folder + file_name):
        file_name = file_name + "_" + "".join(random.choices("0123456789abcdef", k=8))

    # print info
    Utils.info("Folder", folder)
    Utils.info("File", file_name)

    # fix long file names
    if len(folder + file_name) > 254:
        file_name = file_name[:32] + "_" + "".join(random.choices("0123456789abcdef", k=8)) + "." + file_name.split(".")[-1]

    # return False when Exception occurs #
    try:
        # start download #
        with open(folder + file_name, 'wb') as f:
            start = time.time()
            bar_width = 20
            size_downloaded = 0

            # get connection #
            r = downloader.session.get(url, stream=True, headers=headers)
            # r = requests.get(url, stream=True, headers=headers)

            # get content size #
            size_total = r.headers.get('content-length')

            # get remote size #
            if size_total is None or size_total == "0":
                size_total = 1
            else:
                size_total = int(size_total)

            Utils.info("Size", "{} bytes".format(size_total))

            # write to file #
            for chunk in r.iter_content(8192):
                size_downloaded += len(chunk)
                f.write(chunk)

                # build progress bar #
                if size_total == 1:
                    progress = (size_downloaded // (1024 * 20) % bar_width) + 1
                    done = " " * (progress - 1) + "*"
                    todo = " " * (bar_width - progress)
                    size_total = 1
                    percentage = 100
                    length = 7
                else:
                    progress = int(bar_width * size_downloaded / size_total)
                    done = "=" * progress
                    todo = " " * (bar_width - progress)
                    percentage = (size_downloaded / size_total) * 100
                    length = len(str(size_total))
                    if len(done + todo) > bar_width:
                        done = "=" * bar_width
                        todo = ""
                speed = round((size_downloaded / (time.time() - start)) / 1024, 1)
                total_downloaded += len(chunk)
                total_downloaded_mb = round(((total_downloaded / 1024) / 1024), 2)
                print("[{}{}] : {:>{length}} / {} bytes [ {:6.2f}% | {} kB/s ] ({} MB) \r".format(done,
                                                                                                  todo,
                                                                                                  size_downloaded,
                                                                                                  size_total,
                                                                                                  percentage,
                                                                                                  speed,
                                                                                                  total_downloaded_mb,
                                                                                                  length=length),
                      end="")

            if size_total == 1:
                percentage = 100
            else:
                percentage = (size_downloaded / size_total) * 100

            print("[{}] : {} / {} bytes [ {:6.2f}% | {} ] ({} MB)".format("=" * bar_width,
                                                                          size_downloaded,
                                                                          size_total,
                                                                          percentage,
                                                                          "Done",
                                                                          total_downloaded_mb),
                  end=" " * bar_width + "\n\n")

            f.close()
    except Exception as e:
        print("*** EXCEPTION ***")
        print("The following exception occurred " + str(e) + "\n")
        print("Do you want to continue? [y/n]")
        while True:
            confirm = input("> ")
            if confirm == "y":
                print("Continuing... Aborting download and returning False...")
                return False
            elif confirm == "n":
                exit()
            else:
                pass

    # add to checksum #
    if checksum:
        Utils.add(checksum, Utils.get_hash(folder + file_name) + " *" + (folder + file_name).replace("/", "\\"))

    return folder + file_name
