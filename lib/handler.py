import json
import pika
from coralillo.errors import ModelNotFoundError

from .logger import log
from .process import load as process_load, iter_nodes, find
from .errors import ProcessNotFound, CannotMove
from .node import make_node, Node, AsyncNode
from .models import Execution, Pointer


class Handler:
    ''' Handles requests sent to this pvm, a request can be either a `start`
    command or some kind of `step` '''

    def __init__(self, config):
        self.config = config

    def __call__(self, channel, method, properties, body:bytes):
        ''' the main callback of the PVM '''
        message = self.parse_message(body)

        try:
            to_notify = self.call(message)
        except ModelNotFoundError as e:
            return log.error(str(e))
        except CannotMove as e:
            return log.error(str(e))

        for pointer in to_notify:
            channel.basic_publish(
                exchange = '',
                routing_key = self.config['RABBIT_QUEUE'],
                body = json.dumps({
                    'command': 'step',
                    'pointer_id': pointer.id,
                }),
                properties = pika.BasicProperties(
                    delivery_mode = 2, # make message persistent
                ),
            )

        if not self.config['RABBIT_NO_ACK']:
            channel.basic_ack(delivery_tag = method.delivery_tag)

    def call(self, message:dict):
        if message['command'] == 'start':
            execution, pointer, xmliter, current_node = self.get_start(message)
            log.debug('Fetched start for {proc}'.format(
                proc = execution.process_name,
            ))
        elif message['command'] == 'step':
            execution, pointer, xmliter, current_node = self.recover_step(message)
            log.debug('Recovered {proc} at node {node}'.format(
                proc = execution.process_name,
                node = pointer.node_id,
            ))

        pointers = [] # pointers to be notified back
        data = message['data'] if 'data' in message else dict()

        if current_node.can_continue(data):
            pointer.delete()
            next_nodes = current_node.next(xmliter, data)

            for node in next_nodes:
                node()

                if not node.is_end():
                    pointer = self.create_pointer(node, execution)

                    if isinstance(node, AsyncNode):
                        log.debug('execution waiting for step command')
                    else:
                        pointers.append(pointer)
                else:
                    log.debug('Branch of {proc} ended at {node}'.format(
                        proc = execution.process_name,
                        node = node.id,
                    ))

        if execution.proxy.pointers.count() == 0:
            execution.delete()
            log.debug('Execution {exc} finished'.format(
                exc = execution.id,
            ))

        return pointers

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

        filename, xmlfile = process_load(self.config, message['process'])
        xmliter = iter_nodes(xmlfile)
        start_point = find(xmliter, lambda e:e.attrib['class'] == 'start')
        execution = Execution(
            process_name = filename,
        ).save()
        pointer = Pointer(
            node_id = start_point.attrib.get('id'),
        ).save()
        pointer.proxy.execution.set(execution)

        return execution, pointer, xmliter, make_node(start_point)

    def create_pointer(self, node:Node, execution:Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''
        pointer =  Pointer.validate(node_id=node.id).save()
        pointer.proxy.execution.set(execution)

        return pointer

    def recover_step(self, message):
        ''' given an execution id and a pointer from the persistent storage,
        return the asociated process node to continue its execution '''
        if 'pointer_id' not in message:
            raise KeyError('Requested step without pointer id')

        pointer = Pointer.get_or_exception(message['pointer_id'])
        execution = pointer.proxy.execution.get()
        filename, xmlfile = process_load(self.config, execution.process_name)

        assert execution.process_name == filename, 'Inconsisten pointer found'

        xmliter = iter_nodes(xmlfile)
        point = find(
            xmliter,
            lambda e:'id' in e.attrib and e.attrib['id'] == pointer.node_id
        )

        return execution, pointer, xmliter, make_node(point)
