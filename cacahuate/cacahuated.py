#!/usr/bin/env python3
from cacahuate.loop import Loop
from cacahuate.indexes import create_indexes
from cacahuate.models import bind_models
from coralillo import Engine
from itacate import Config
import time
import os


def main():
    # Load the config
    config = Config(os.path.dirname(os.path.realpath(__file__)))
    config.from_object('cacahuate.settings')
    config.from_envvar('CACAHUATE_SETTINGS', silent=True)

    # Set the timezone
    os.environ['TZ'] = config['TIMEZONE']
    time.tzset()

    # Logging stuff
    if not config['TESTING']:
        from cacahuate.logger import init_logging

        init_logging(config)

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
