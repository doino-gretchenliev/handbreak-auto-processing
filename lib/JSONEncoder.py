from flask.json import JSONEncoder

from lib.media_file_state import MediaFileState


class JSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, MediaFileState):
                return obj.value
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)