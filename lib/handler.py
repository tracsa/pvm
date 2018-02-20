import json

from .logger import log
from .process import load as process_load
from .errors import ProcessNotFound


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body:bytes):
        try:
            message = self.parse_message(body)
        except Exception as e:
            log.error('Message didnt pass validation: ' + str(e))

        if message['command'] == 'start':
            current_node = self.get_start()
        elif message['command'] == 'step':
            current_node = self.recover_step()

        while current_node.can_continue():
            current_node = current_node.next()
            current_node()

            if current_node.is_end():
                log.info('Execution of branch ended')
                break
        else:
            self.save_execution()

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
        if 'process' not in message:
            return log.warning('Requested start without process name')

        try:
            xml = process_load(self.config, message['process'])
        except ProcessNotFound as e:
            return log.warning(str(e))

        try:
            start_point = xml.find(".//*[@class='start']")
        except Exception:
            return log.warning('Malformed xml')
