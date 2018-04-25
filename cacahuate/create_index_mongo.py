from flask import Flask,current_app
from flask_pymongo import PyMongo
import pymongo

def create_index(config):

    app = Flask(__name__)
    with app.app_context():
        app.config.from_object('cacahuate.settings')
        app.config.from_envvar('CACAHUATE_SETTINGS', silent=True)

        # Create index
        mongo = PyMongo(app)
        execution = mongo.db[config['MONGO_EXECUTION_COLLECTION']]
        history = mongo.db[config['MONGO_HISTORY_COLLECTION']]
        '''Drop indexes '''
        # execution.drop_indexes()
        execution.create_index("id", unique=True)
        execution.create_index("status")
        execution.create_index("started_at")
        execution.create_index("finished_at")

        history.create_index("id", unique=True)
        history.create_index("status")
        history.create_index("execution.id")
        history.create_index("started_at")
        history.create_index("finished_at")

        '''list indexes '''
        # execution.index_information()


