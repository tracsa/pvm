from coralillo import Engine
from itacate import Config
import os
import pytest
import sys
from pymongo import MongoClient

from cacahuate.models import bind_models


@pytest.fixture
def config():
    ''' Returns a fully loaded configuration dict '''
    con = Config(
                os.path.join(
                            os.path.dirname(os.path.realpath(__file__)), '..'
                            )
                )
    con.from_object('cacahuate.settings')
    con.from_envvar('CACAHUATE_SETTINGS', silent=True)

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


@pytest.fixture
def client():
    ''' makes and returns a testclient for the flask application '''
    from cacahuate.http.wsgi import app

    return app.test_client()


@pytest.fixture
def mongo():
    con = config()
    client = MongoClient()
    db = client[con['MONGO_DBNAME']]

    collection = db[con['MONGO_HISTORY_COLLECTION']]
    collection.drop()

    return collection
