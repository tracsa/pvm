import json

from .logger import log
from .process import load as process_load
from .errors import ProcessNotFound
from .node import make_node


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body:bytes):
        ''' the main callback of the PVM '''
        message = self.parse_message(body)

        if message['command'] == 'start':
            current_node = self.get_start(message)
        elif message['command'] == 'step':
            current_node = self.recover_step()

        if current_node.can_continue():
            next_nodes = current_node.next()

            for node in next_nodes:
                node()

        if current_node.is_end():
            self.end_execution()
        else:
            self.save_execution()

        channel.basic_ack(delivery_tag = method.delivery_tag)

    def parse_message(self, body:bytes):
        ''' validates a received message against all possible needed fields
        and structure '''
        try:
            message = json.loads(body)
        except json.decoder.JSONDecodeError:
            raise ValueError('Message is not json')

        if 'command' not in message:
            raise KeyError('Malformed message: must contain command keyword')

        if message['command'] not in self.config['COMMANDS']:
            raise ValueError('Command not supported: {}'.format(message['command']))

        return message

    def get_start(self, message:dict):
        ''' finds the start node of a given process '''
        if 'process' not in message:
            raise KeyError('Requested start without process name')

        xml = process_load(self.config, message['process'])
        start_point = xml.find(".//*[@class='start']")

        return make_node(start_point)

    def save_execution(self):
        ''' persists the execution in the current state '''
        pass
