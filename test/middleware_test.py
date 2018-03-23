from flask import json

def test_requires_json(client):
    res = client.get('/')

    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/json'

    res = client.post('/')

    assert res.status_code == 400
    assert res.headers['Content-Type'] == 'application/json'
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'Content-Type must be application/json',
            'where': 'request.headers.content_type',
        }],
    }

    res = client.post('/', headers={
        'Content-Type': 'application/json',
    }, data='not json')

    assert res.status_code == 400
    assert res.headers['Content-Type'] == 'application/json'
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'request body is not valid json',
            'where': 'request.body',
        }],
    }

    res = client.post('/', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({'a':1}))

    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/json'
    assert json.loads(res.data) == { 'a': 1 }
