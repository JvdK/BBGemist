import inspect
import sys

from Download import Download

"""
Main Action Class
"""


class Action:
    name = "Undefined Action"
    description = "No description given."

    @staticmethod
    def action():
        raise NotImplementedError

    def __str__(self):
        return self.__class__.__name__


"""
Actions
"""


# TODO: Split download features


class DownloadBlackboardCourse(Action):
    code = "1"
    name = "Download course files"
    description = "Download a Blackboard course to your computer."

    @staticmethod
    def action():
        Download()


class DownloadBlackboardCourseSubmissions(Action):
    code = "2"
    name = "Download course files and submissions"
    description = "Download a Blackboard course to your computer."

    @staticmethod
    def action():
        Download()


class DownloadBlackboardCourseAll(Action):
    code = "3"
    name = "Download course files and submissions and details (i.e. EVERYTHING)"
    description = "Download a Blackboard course to your computer."

    @staticmethod
    def action():
        Download()


actions = []
codes = []
width = 0

for name, obj in inspect.getmembers(sys.modules[__name__]):
    if inspect.isclass(obj):
        if hasattr(obj, "code") and hasattr(obj, "name") and hasattr(obj, "description"):
            actions.append(obj)
            codes.append(obj.code)

for code in codes:
    if len(code) > width:
        width = len(code)
