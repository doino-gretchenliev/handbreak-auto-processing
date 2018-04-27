from flask.json import JSONEncoder
import calendar
from datetime import datetime

from lib.media_file_states import MediaFileStates


class JSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, MediaFileStates):
                return obj.value
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)