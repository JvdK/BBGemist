BBGemist (Blackboard Downloader)
================================
The goal of this program is to download course data from the University of Twente Blackboard archive, which
is available until 14 September 2020. It tries to download all course files available on pages and will try to download
all assignments and submissions as well.

GUI Version
===========
There is a Blackboard Scraper with a GUI available that downloads all files including the Blackboard websites itself 
available in the [scraper-gui](https://github.com/JvdK/BBGemist/tree/scraper-gui) branch. 

https://github.com/JvdK/BBGemist/tree/scraper-gui

Installation Instructions
-------------------------
This program requires that you have installed Python 3 from https://www.python.org/

To install the dependencies run:
````
python -m pip install -r requirements.txt
````

To run the program, go to the folder that contains the code and then go one level up and run:
````
python BBGemist
````

You can update the download path in `Config.py`, the folder will be automatically created:
```python
DOWNLOAD_PATH = "D:/Blackboard/"
```

A self-contained .exe for Windows file might be available at a later time. (Soonᵀᴹ)