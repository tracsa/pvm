import os
import logging

base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

# Testing and log stuff
TESTING = False
LOG_LEVEL = logging.INFO

# Where to store xml files
XML_PATH = os.path.join(base_dir, 'xml')

# Rabbitmq
RABBIT_HOST = 'localhost'
RABBIT_QUEUE = 'pvm_process'
RABBIT_NOTIFY_EXCHANGE = 'pvm_notify'
RABBIT_CONSUMER_TAG = 'pvm_consumer_1'
RABBIT_NO_ACK = True

# Mongodb
MONGO_DBNAME = 'pvm'
MONGO_HISTORY_COLLECTION = 'history'

# Time stuff
TIMEZONE = 'UTC'

# Supported commands for the PVM
COMMANDS = [
    'step',
]

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

LDAP_URI = "ldap://localhost:389"
LDAP_SSL = True
LDAP_DOMAIN = "local"
