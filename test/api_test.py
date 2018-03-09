from flask import json

from .context import *

def test_continue_process_requires(client):
    res = client.post('/v1/pointer')

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': '',
                'i18n': 'errors.missing_field',
                'field': 'execution_id',
            },
            {
                'detail': '',
                'i18n': 'errors.missing_field',
                'field': 'execution_id',
            },
        ],
    }

def test_can_continue_process(client):
    res = client.post('/v1/pointer')

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            {
                '_type': 'pointer',
                'id': '',
                'node_id': '',
            },
        ]
    }

def test_can_query_process_status(client):
    res = client.get('/v1/node/{}')

    assert res.status_code == 200
    assert res.data == {
        'data': [
            {
                '_type': 'node',
                'id': '',
                'data': {},
            },
        ]
    }

def test_execution_start(client, models):
    assert lib.models.Execution.count() == 0
    assert lib.models.Pointer.count() == 0

    res = client.post('/v1/execution')

    assert res.status_code == 201
    assert res.json() == {
        'data': {
            '_type': 'execution',
            'id': '',
            'process_name': 'simple',
        },
    }

    assert lib.models.Execution.count() == 1
    assert lib.models.Pointer.count() == 1
