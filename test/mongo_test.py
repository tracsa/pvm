'''
Tests the cacahuate.mongo module
'''
from datetime import datetime

from cacahuate.mongo import json_prepare


def test_json_prepare():
    obj_id = 'some id'
    started_at = datetime(2020, 9, 29)
    finished_at = datetime(2020, 10, 1)

    obj = {
        '_id': obj_id,
        'started_at': started_at,
        'finished_at': finished_at,
        'a': 'hola',
    }

    prepared_obj = {
        'started_at': '2020-09-29T00:00:00',
        'finished_at': '2020-10-01T00:00:00',
        'a': 'hola',
    }

    assert json_prepare(obj) == prepared_obj

    assert obj['_id'] == obj_id
    assert obj['started_at'] == started_at
    assert obj['finished_at'] == finished_at
