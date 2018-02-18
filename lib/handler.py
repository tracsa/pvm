import json

from .logger import log
import .process


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body:bytes):
        try:
            message = json.loads(body)
        except json.decoder.JSONDecodeError:
            return log.warning('Could not json-decode message')

        if 'command' not in message:
            return log.warning('Malformed message: must contain command keyword')

        if message['command'] not in self.config['COMMANDS']:
            return log.warning('Command not supported: {}'.format(message['command']))

        getattr(self, message['command'])(message)

    def start(self, message:dict):
        if 'process' not in message:
            return log.warning('Requested start without process name')

        try:
            xml = process.load(self.config, message['process'])
        except ProcessNotFound:
            return log.warning('File for requested process could not be found')
