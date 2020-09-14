BBGemist (Blackboard Downloader)
================================
The goal of this program is to download course data from the University of Twente Blackboard archive, which
is available until 14 September 2020. It tries to download all course files, assignments and submissions available.
The web pages will be scraped and modified to work without a web-server to create a local Blackboard copy.

Installation Instructions
-------------------------
This program requires that you have installed Python 3.7 from https://www.python.org/

To install the dependencies run:
````
python -m pip install -r requirements.txt
````

To run the program use:
````
python BlackboardScraper.py
````

Compile EXE
-----------
Install pyinstaller:
```
pip install pyinstaller
```
To create the EXE run the following command:
```
pyinstaller.exe --noconsole --onefile --icon=bb-icon2.ico BlackboardScraper.py
```
