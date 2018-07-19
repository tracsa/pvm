from base64 import b64encode
from flask import json
from random import choice
from string import ascii_letters


def test_unexistent_backend(client):
    mth = ''.join(choice(ascii_letters) for _ in range(6))
    res = client.post('/v1/auth/signin/{}'.format(mth))

    assert res.status_code == 500
    assert json.loads(res.data) == {
        'errors': [{
            'detail': '500 Internal Server Error: Provider {} not enabled'
                      .format(mth),
            'where': 'server',
        }],
    }


def test_login_wrong_user(client):
    res = client.post('/v1/auth/signin/hardcoded')

    assert res.status_code == 401
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'username is required',
                'code': 'validation.required',
                'where': 'request.body.username',
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


def test_login_token(client):
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


def test_ldap_backend():
    from cacahuate.auth.backends.ldap import LdapAuthProvider  # noqa

    assert LdapAuthProvider


def test_anyone_backend():
    from cacahuate.auth.backends.anyone import AnyoneAuthProvider  # noqa

    assert AnyoneAuthProvider


def test_impersonate_backend():
    from cacahuate.auth.backends.impersonate import ImpersonateAuthProvider  # noqa

    assert ImpersonateAuthProvider
