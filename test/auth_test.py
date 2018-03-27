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
                'detail': 'Provided user credentials are invalid',
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

    token = data['data']['token']

    assert False, 'can login using token'
