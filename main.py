from lib.loop import Loop
from itacate import Config
import time
import os

if __name__ == '__main__':
    # Load the config
    config = Config(os.path.dirname(os.path.realpath(__file__)))
    config.from_pyfile('settings.py')
    config.from_envvar('PVM_SETTINGS', silent=False)

    # Set the timezone
    os.environ['TZ'] = config['TIMEZONE']
    time.tzset()

    # Logging stuff
    if not config['TESTING']:
        from lib.logger import init_logging

        init_logging(config)

    # start the loop
    loop = Loop(config)
    loop.start()
