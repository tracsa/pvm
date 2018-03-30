import json
import pika
from coralillo.errors import ModelNotFoundError

from .logger import log
from .xml import Xml
from .errors import ProcessNotFound, CannotMove
from .node import make_node, Node, AsyncNode
from .models import Execution, Pointer


class Handler:
    ''' The actual process machine, it is in charge of moving the pointers
    among the graph of nodes '''

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
        execution, pointer, xml, current_node = self.recover_step(message)

        pointers = [] # pointers to be notified back

        # node's lifetime ends here
        pointer.delete()
        next_nodes = current_node.next(xml, execution)

        for node in next_nodes:
            # node's begining of life
            node.wakeup()

            if not node.is_end():
                # End nodes don't create pointers, their lifetime ends here
                pointer = self.create_pointer(node, execution)

                if not isinstance(node, AsyncNode):
                    # Sync nodes trigger execution of the next node right away
                    pointers.append(pointer)

        if execution.proxy.pointers.count() == 0:
            execution.delete()

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

    def create_pointer(self, node:Node, execution:Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''
        pointer =  Pointer.validate(node_id=node.element.getAttribute('id')).save()
        pointer.proxy.execution.set(execution)

        return pointer

    def recover_step(self, message:dict):
        ''' given an execution id and a pointer from the persistent storage,
        return the asociated process node to continue its execution '''
        if 'pointer_id' not in message:
            raise KeyError('Requested step without pointer id')

        pointer = Pointer.get_or_exception(message['pointer_id'])
        execution = pointer.proxy.execution.get()
        xml = Xml.load(self.config, execution.process_name)

        assert execution.process_name == xml.name, 'Inconsisten pointer found'

        point = xml.find(
            lambda e:e.getAttribute('id') == pointer.node_id
        )

        return execution, pointer, xml, make_node(point)
