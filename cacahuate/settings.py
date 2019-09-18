import os

base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

# Rabbitmq
RABBIT_HOST = 'localhost'
RABBIT_QUEUE = 'cacahuate_process'
RABBIT_NOTIFY_EXCHANGE = 'charpe_notify'
RABBIT_CONSUMER_TAG = 'cacahuate_consumer_1'
RABBIT_NO_ACK = True

# Default logging config
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(levelname)s] %(message)s - %(name)s:%(lineno)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        # 'charpe': {
        #     'class': 'charpe.CharpeHandler',
        #     'level': 'ERROR',
        #     'host': RABBIT_HOST,
        #     'medium': 'email',
        #     'exchange': RABBIT_NOTIFY_EXCHANGE,
        #     'service_name': 'cacahuate',
        #     'params': {
        #         'recipient': 'support@example.com',
        #         'subject': '[cacahuate] Server Error',
        #         'template': 'server-error',
        #     },
        # },
    },
    'loggers': {
        'cacahuate': {
            'handlers': ['console'],
            'level': 'INFO',
            'filters': [],
        },
    },
}

# Where to store xml files
XML_PATH = os.path.join(base_dir, 'xml')

# Where to store template files
TEMPLATE_PATH = os.path.join(base_dir, 'template')

# Mongodb
MONGO_URI = os.getenv('CACAHUATE_MONGO_URI', 'mongodb://localhost/cacahuate')
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

# The different providers that can be used for log in
ENABLED_LOGIN_PROVIDERS = [
    'ldap',
]

# Providers enabled for locating people in the system
ENABLED_HIERARCHY_PROVIDERS = [
    'anyone',
    'backref',
]

# custom login providers
CUSTOM_LOGIN_PROVIDERS = {
    # 'name': 'importable.path',
}

# custom hierarchy providers
CUSTOM_HIERARCHY_PROVIDERS = {
    # 'name': 'importable.path',
}

# will be sent to charpe for rendering of emails
GUI_URL = 'http://localhost:8080'

# The 'impersonate' login module, when enabled, uses this to login
IMPERSONATE_PASSWORD = 'set me to passlib.hash.pbkdf2_sha256.hash("something")'

# Invalid filters for query string
INVALID_FILTERS = (
    'limit',
    'offset',
)
