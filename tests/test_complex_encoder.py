import json
from lib.complex_encoder import ComplexEncoder
from datetime import datetime


def test_complex_encoder():
    obj = {"foo": "bar", "date": datetime.fromisoformat("2025-07-03T17:24:40")}
    serialization = json.dumps(obj, indent=2, sort_keys=True, cls=ComplexEncoder)

    assert serialization == (
        "{" '\n  "date": "2025-07-03T17:24:40",' '\n  "foo": "bar"' "\n}"
    )
