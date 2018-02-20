import os
import sys
from itacate import Config

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import lib
import lib.xml
import lib.process
import lib.handler
import lib.node

def get_testing_config(overwrites:dict=None):
    config = Config(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
    config.from_pyfile('settings.py')

    if overwrites is not None:
        config.from_mapping(overwrites)

    return config
