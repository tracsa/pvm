import os

base_dir = os.path.dirname(os.path.realpath(__file__))

TESTING = False

# Where to store xml files
XML_PATH = os.path.join(base_dir, 'xml')

# Rabbitmq
RABBIT_HOST = 'localhost'
RABBIT_QUEUE = 'pvm_process'
RABBIT_CONSUMER_TAG = 'pvm_consumer_1'

# Time stuff
TIMEZONE = 'UTC'
