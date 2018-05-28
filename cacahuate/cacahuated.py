#!/usr/bin/env python3
from coralillo import Engine
from itacate import Config
import logging
import logging.config
import os
import time

from cacahuate.indexes import create_indexes
from cacahuate.loop import Loop
from cacahuate.models import bind_models


def main():
    # Load the config
    config = Config(os.path.dirname(os.path.realpath(__file__)))
    config.from_object('cacahuate.settings')
    config.from_envvar('CACAHUATE_SETTINGS', silent=True)

    # Set the timezone
    os.environ['TZ'] = config['TIMEZONE']
    time.tzset()

    # Setup logging
    logging.config.dictConfig(config['LOGGING'])

    # Load the models
    eng = Engine(
        host=config['REDIS_HOST'],
        port=config['REDIS_PORT'],
        db=config['REDIS_DB'],
    )
    bind_models(eng)

    # Create mongo indexes
    create_indexes(config)

    # start the loop
    loop = Loop(config)
    loop.start()


if __name__ == '__main__':
    main()
