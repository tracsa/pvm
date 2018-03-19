from coralillo import Engine
from itacate import Config
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import lib
import lib.xml
import lib.handler
import lib.node
import lib.errors
import lib.models

@pytest.fixture
def config():
    ''' Returns a fully loaded configuration dict '''
    con = Config(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
    con.from_pyfile('settings.py')
    con.from_envvar('PVM_SETTINGS', silent=False)

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
    lib.models.bind_models(engine)

@pytest.fixture
def client():
    ''' makes and returns a testclient for the flask application '''
    from pvm_api import app

    return app.test_client()
