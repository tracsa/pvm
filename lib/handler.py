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

        if message['command'] == 'start':
            current_node = self.get_start_node()
        elif message['command'] == 'step':
            current_node = self.recover_step()

        while current_node.can_reach_next_step():
            current_node = current_node.next()

            if current_node.is_end():
                log.info('Execution of branch ended')
                break
        else:
            self.save_execution()

    def get_start_node(self, message:dict):
        if 'process' not in message:
            return log.warning('Requested start without process name')

        try:
            xml = process.load(self.config, message['process'])
        except ProcessNotFound:
            return log.warning('File for requested process could not be found')
