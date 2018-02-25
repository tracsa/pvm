import json

from .logger import log
from .process import load as process_load, iter_nodes, find
from .errors import ProcessNotFound
from .node import make_node, Node
from .models import Execution, Pointer


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body:bytes):
        ''' the main callback of the PVM '''
        message = self.parse_message(body)

        if message['command'] == 'start':
            execution, pointer, xmliter, current_node = self.get_start(message)
            log.debug('Fetched start node')
        elif message['command'] == 'step':
            execution, pointer, xmliter, current_node = self.recover_step(message)
            log.debug('Recovered saved node')

        if current_node.can_continue():
            pointer.delete()
            next_nodes = current_node.next(xmliter)

            for node in next_nodes:
                node()

                if not node.is_end():
                    self.create_pointer(node, execution)

        if execution.proxy.pointers.count() == 0:
            execution.delete()

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
            raise ValueError('Command not supported: {}'.format(
                message['command']
            ))

        return message

    def get_start(self, message:dict):
        ''' finds the start node of a given process '''
        if 'process' not in message:
            raise KeyError('Requested start without process name')

        xmliter = iter_nodes(process_load(self.config, message['process']))
        start_point = find(xmliter, lambda e:e.attrib['class'] == 'start')
        execution = Execution(
            process_name = '',
        ).save()
        pointer = Pointer(
            node_id = start_point.attrib.get('id'),
        ).save()
        pointer.proxy.execution.set(execution)

        return execution, pointer, xmliter, make_node(start_point)

    def create_pointer(self, node:Node, execution:Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''

    def delete_pointer(self):
        ''' given an execution pointer, delete the persistent storage asociated
        to it. This means that such execution branch has ended or the asociated
        process was killed '''

    def recover_step(self, message):
        ''' given an execution id and a pointer from the persistent storage,
        return the asociated process node to continue its execution '''
        if 'pointer_id' not in message:
            raise KeyError('Requested continue without pointer id')

        pointer = Pointer.get_or_exception(message['pointer_id'])
        execution = pointer.proxy.execution.get()
        xmliter = iter_nodes(process_load(self.config, execution.process_name))
        point = find(xmliter, lambda e:'id' in e.attrib and e.attrib['id'] == pointer.node_id)

        return execution, pointer, xmliter, make_node(point)
