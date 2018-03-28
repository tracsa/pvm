from flask import json
from random import choice
from string import ascii_letters
import pytest

from coralillo import Engine
from itacate import Config
import os
import pytest

from pvm.models import bind_models, Token
from base64 import b64encode

@pytest.fixture
def config():
    ''' Returns a fully loaded configuration dict '''
    con = Config(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
    con.from_pyfile('settings.py')
    con.from_envvar('PVM_SETTINGS', silent=True)

    return con

@pytest.fixture
def models():
    ''' Binds the models to a coralillo engine, returns nothing '''
    con = config()
    engine = Engine(
        host=con['REDIS_HOST'],
        port=con['REDIS_PORT'],
        db=con['REDIS_DB'],
    )
    engine.lua.drop(args=['*'])

    bind_models(engine)

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

@pytest.mark.skip
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
