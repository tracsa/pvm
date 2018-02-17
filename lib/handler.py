import json

from .logger import log


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body):
        try:
            message = json.loads(body)
        except json.decoder.JSONDecodeError:
            return log.warning('Could not json-decode message')

        print(message)
