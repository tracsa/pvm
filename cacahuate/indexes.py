import pymongo
from pymongo import MongoClient


def create_indexes(config):
    # Create index
    mongo = MongoClient(config['MONGO_URI'])
    db = getattr(mongo, config['MONGO_DBNAME'])

    db.execution.create_index("id", unique=True)
    db.execution.create_index("status")
    db.execution.create_index("started_at")
    db.execution.create_index("finished_at")

    db.history.create_index("status")
    db.history.create_index("execution.id")
    db.history.create_index("started_at")
    db.history.create_index("finished_at")
