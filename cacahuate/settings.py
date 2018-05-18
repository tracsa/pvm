import os
import logging

base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

# Testing and log stuff
TESTING = False
LOG_LEVEL = logging.DEBUG

# Where to store xml files
XML_PATH = os.path.join(base_dir, 'xml')

# Rabbitmq
RABBIT_HOST = 'localhost'
RABBIT_QUEUE = 'cacahuate_process'
RABBIT_NOTIFY_EXCHANGE = 'cacahuate_notify'
RABBIT_CONSUMER_TAG = 'cacahuate_consumer_1'
RABBIT_NO_ACK = True

# Mongodb
MONGO_URI = 'mongodb://localhost/cacahuate'
MONGO_DBNAME = 'cacahuate'
POINTER_COLLECTION = 'pointer'
EXECUTION_COLLECTION = 'execution'

# Defaults for pagination
PAGINATION_LIMIT = 20
PAGINATION_OFFSET = 0

# Time stuff
TIMEZONE = 'UTC'

# Supported commands for cacahuate
COMMANDS = [
    'step',
    'cancel',
]

# For ephimeral objects, like executions and pointers
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# LDAP settings
LDAP_URI = "ldap://localhost:389"
LDAP_SSL = True
LDAP_DOMAIN = "local"
LDAP_BASE = "DC=local"

# custom login providers
LOGIN_PROVIDERS = {
    # 'name': 'importable.path',
}

# custom hierarchy providers
HIERARCHY_PROVIDERS = {
    # 'name': 'importable.path',
}
