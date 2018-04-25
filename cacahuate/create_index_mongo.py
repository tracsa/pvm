import pymongo
from pymongo import MongoClient


def create_index(config):
    # Create index
    execution = MongoClient().cacahuate.execution
    history = MongoClient().cacahuate.history

    execution.create_index("id", unique=True)
    execution.create_index("status")
    execution.create_index("started_at")
    execution.create_index("finished_at")

    history.create_index("id", unique=True)
    history.create_index("status")
    history.create_index("execution.id")
    history.create_index("started_at")
    history.create_index("finished_at")
