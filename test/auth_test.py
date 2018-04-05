from base64 import b64encode
from flask import json
from random import choice
from string import ascii_letters


def test_unexistent_backend(client):
    mth = ''.join(choice(ascii_letters) for _ in range(6))
    res = client.post('/v1/auth/signin/{}'.format(mth))

    assert res.status_code == 404
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'Auth backend not found: {}'.format(mth),
            'where': 'request.url',
        }],
    }


def test_login_wrong_user(client):
    res = client.post('/v1/auth/signin/hardcoded')

    assert res.status_code == 401
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': '401 Unauthorized: Provided user credentials are invalid',
                'where': 'request.body',
            },
        ],
    }


def test_login(client):
    res = client.post('/v1/auth/signin/hardcoded', data={
        'username': 'juan',
        'password': '123456',
    })

    assert res.status_code == 200

    data = json.loads(res.data)

    assert 'data' in data
    assert 'token' in data['data']


def test_login_token(client, models):
    res = client.post('/v1/auth/signin/hardcoded', data={
        'username': 'juan',
        'password': '123456',
    })
    data = json.loads(res.data)

    user = data['data']['username']
    token = data['data']['token']

    auth_string = '{}:{}'.format(user, token)
    b64_string = b64encode(auth_string.encode('utf-8')).decode('ascii')
    auth_header = 'Basic {}'.format(b64_string)

    res = client.get('/v1/auth/whoami', headers={
        'Authorization': auth_header
    })
    data = json.loads(res.data)

    assert res.status_code == 200
    assert data['data']['_type'] == 'user'
    assert data['data']['identifier'] == user
