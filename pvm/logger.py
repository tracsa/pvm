import logging
import sys
import simplejson as json

log = logging.getLogger('fleety-reporter')
log.setLevel(logging.DEBUG)


class BrokerHandler(logging.Handler):

    def __init__(self, redis=None, channel=None):
        super().__init__()

        self.redis = redis
        self.channel = channel

    def emit(self, record):
        try:
            traceback = self.format(record)

            message = {
                'event': 'server-error',
                'data': {
                    'user': None,
                    'traceback': traceback,
                    'get_data': None,
                    'post_data': None,
                    'method': None,
                    'path': None,
                    'org_name': None,
                },
            }

            self.redis.publish(self.channel, json.dumps(message))
        except Exception:
            self.handleError(record)

    def parse_dict(self, data):
        return '\n'.join(
            '{}: {}'.format(key, value)
            for key, value in data.items()
        )


def init_logging(config):
    # Debug messages to stderr
    formatter = logging.Formatter(
                                fmt='[%(levelname)s] %(message)s - '
                                '%(filename)s:%(lineno)d',
                                datefmt='%Y-%m-%d %H:%M:%S %z'
                )

    file_handler = logging.StreamHandler(stream=sys.stderr)
    file_handler.setLevel(config['LOG_LEVEL'])
    file_handler.setFormatter(formatter)

    # Send messages to broker
    # broker_handler = BrokerHandler()
    # broker_handler.setLevel(logging.ERROR)

    # log.addHandler(broker_handler)
    log.addHandler(file_handler)
