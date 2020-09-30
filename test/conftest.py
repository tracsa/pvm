from coralillo import Engine
from itacate import Config
import os
import pytest
from pymongo import MongoClient

from cacahuate.models import bind_models as bimo

TESTING_SETTINGS = {
    'CUSTOM_LOGIN_PROVIDERS': {
        'hardcoded': 'test.hardcoded_login',
    },
    'CUSTOM_HIERARCHY_PROVIDERS': {
        'hardcoded': 'test.hardcoded_hierarchy',
        'noparam': 'test.noparam_hierarchy',
    },
    'PROCESS_ENV': {
        'FOO': 'var',
    },
    'TEMPLATE_PATH': os.path.join(os.path.dirname(__file__), 'templates'),
}


@pytest.fixture
def config():
    ''' Returns a fully loaded configuration dict '''
    con = Config(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '..'
        )
    )

    con.from_object('cacahuate.settings')
    con.from_mapping(TESTING_SETTINGS)

    return con


@pytest.fixture(autouse=True)
def clear_mongo(config):
    client = MongoClient()
    db = client[config['MONGO_DBNAME']]

    collection = db[config['POINTER_COLLECTION']]
    collection.drop()

    collection_execution = db[config['EXECUTION_COLLECTION']]
    collection_execution.drop()


@pytest.fixture(autouse=True)
def bind_models(config):
    ''' Binds the models to a coralillo engine, returns nothing '''
    engine = Engine(
        host=config['REDIS_HOST'],
        port=config['REDIS_PORT'],
        db=config['REDIS_DB'],
    )
    engine.lua.drop(args=['*'])

    bimo(engine)


@pytest.fixture
def client():
    ''' makes and returns a testclient for the flask application '''
    from cacahuate.http.wsgi import app

    app.config.from_mapping(TESTING_SETTINGS)

    return app.test_client()


@pytest.fixture
def mongo(config):
    client = MongoClient()
    db = client[config['MONGO_DBNAME']]

    return db
