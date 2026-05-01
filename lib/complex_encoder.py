from datetime import datetime
from json import JSONEncoder


class ComplexEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "jsonable"):
            return obj.jsonable()
        else:
            return JSONEncoder.default(self, obj)
