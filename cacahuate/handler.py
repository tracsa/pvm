from coralillo.errors import ModelNotFoundError
from datetime import datetime
from importlib import import_module
from pymongo import MongoClient
import logging
import pika
import pymongo
import simplejson as json

from cacahuate.errors import CannotMove, ElementNotFound, InconsistentState, \
    MisconfiguredProvider, EndOfProcess
from cacahuate.models import Execution, Pointer, User
from cacahuate.xml import Xml
from cacahuate.node import make_node, Exit, Validation, UserAttachedNode
from cacahuate.grammar import Condition

LOGGER = logging.getLogger(__name__)


class Handler:
    ''' The actual process machine, it is in charge of moving the pointers
    among the graph of nodes '''

    def __init__(self, config):
        self.config = config
        self.mongo = None

    def __call__(self, channel, method, properties, body: bytes):
        ''' the main callback of cacahuate '''
        message = json.loads(body)

        if message['command'] == 'cancel':
            self.cancel_execution(message)
        elif message['command'] == 'step':
            try:
                self.call(message, channel)
            except (ModelNotFoundError, CannotMove, ElementNotFound,
                    MisconfiguredProvider, InconsistentState
                    ) as e:
                LOGGER.error(str(e))
        else:
            LOGGER.warning(
                'Unrecognized command {}'.format(message['command'])
            )

        if not self.config['RABBIT_NO_ACK']:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def call(self, message: dict, channel):
        pointer, user, input = self.recover_step(message)
        execution = pointer.proxy.execution.get()

        xml = Xml.load(self.config, execution.process_name, direct=True)
        xmliter = iter(xml)

        node = make_node(xmliter.find(
            lambda e: e.getAttribute('id') == pointer.node_id
        ), xmliter)

        # node's lifetime ends here
        self.teardown(node, pointer, user, input)

        # compute the next node in the sequence
        try:
            next_node, state = self.next(xml, node, execution)
        except EndOfProcess:
            # finish the execution
            return self.finish_execution(execution)

        # node's begining of life
        qdata = self.wakeup(next_node, execution, channel, state)

        # Sync nodes are queued immediatly
        if qdata:
            new_pointer, new_input = qdata

            channel.queue_declare(
                queue=self.config['RABBIT_QUEUE'],
                durable=True
            )

            channel.basic_publish(
                exchange='',
                routing_key=self.config['RABBIT_QUEUE'],
                body=json.dumps({
                    'command': 'step',
                    'pointer_id': new_pointer.id,
                    'user_identifier': '__system__',
                    'input': new_input,
                }),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
            )

    def next(self, xml, node, execution):
        ''' Given a position in the script, return the next position '''
        # Return next node by simple adjacency, works for actions and accepted
        # validations

        collection = self.get_mongo()[
            self.config['EXECUTION_COLLECTION']
        ]
        state = next(collection.find({'id': execution.id}))

        try:
            while True:
                node = node.next(
                    xml,
                    state,
                    self.get_mongo(),
                    self.config
                )

                # refresh state because previous call might have changed it
                state = next(collection.find({'id': execution.id}))

                if node.id in state['state']['items']:
                    if state['state']['items'][node.id]['state'] == 'valid':
                        continue

                return node, state
        except StopIteration:
            # End of process
            raise EndOfProcess

    def wakeup(self, node, execution, channel, state):
        ''' Waking up a node often means to notify someone or something about
        the execution, this is the first step in node's lifecycle '''

        # create a pointer in this node
        pointer = self.create_pointer(node, execution)
        LOGGER.debug('Created pointer p:{} n:{} e:{}'.format(
            pointer.id,
            node.id,
            execution.id,
        ))

        # notify someone
        if isinstance(node, UserAttachedNode):
            notified_users = self.notify_users(node, pointer, channel, state)
        else:
            notified_users = []

        if not node.is_async():
            input = node.work(self.config, state, channel, self.get_mongo())
        else:
            input = []

        # update registry about this pointer
        collection = self.get_mongo()[self.config['POINTER_COLLECTION']]
        collection.insert_one(node.pointer_entry(
            execution, pointer, notified_users
        ))

        # mark this node as ongoing
        collection = self.get_mongo()[self.config['EXECUTION_COLLECTION']]
        collection.update_one({
            'id': execution.id,
        }, {
            '$set': {
                'state.items.{}.state'.format(node.id): 'ongoing',
            },
        })

        # nodes with forms are not queued
        if not node.is_async():
            return pointer, input

    def teardown(self, node, pointer, user, input):
        ''' finishes the node's lifecycle '''
        execution = pointer.proxy.execution.get()
        execution.proxy.actors.add(user)

        actor_json = {
            '_type': 'actor',
            'state': 'valid',
            'user': user.to_json(include=[
                '_type',
                'fullname',
                'identifier',
            ]),
            'forms': input,
        }

        # update pointer
        collection = self.get_mongo()[self.config['POINTER_COLLECTION']]
        collection.update_one({
            'id': pointer.id,
        }, {
            '$set': {
                'finished_at': datetime.now(),
                'actors.items.{identifier}'.format(
                    identifier=user.identifier,
                ): actor_json,
            },
        })

        values = self.compact_values(input)

        # update state
        collection = self.get_mongo()[
            self.config['EXECUTION_COLLECTION']
        ]
        collection.update_one({
            'id': execution.id,
        }, {
            '$set': {**{
                'state.items.{node}.state'.format(node=node.id): 'valid',
                'state.items.{node}.actors.items.{identifier}'.format(
                    node=node.id,
                    identifier=user.identifier,
                ): actor_json,
                'actors.{}'.format(node.id): user.identifier,
            }, **values},
        })

        LOGGER.debug('Deleted pointer p:{} n:{} e:{}'.format(
            pointer.id,
            pointer.node_id,
            execution.id,
        ))

        pointer.delete()

    def finish_execution(self, execution):
        """ shuts down this execution and every related object """
        mongo = self.get_mongo()
        collection = mongo[self.config['EXECUTION_COLLECTION']]
        collection.update_one({
            'id': execution.id,
        }, {
            '$set': {
                'status': 'finished',
                'finished_at': datetime.now()
            }
        })

        LOGGER.debug('Finished e:{}'.format(execution.id))

        execution.delete()

    def compact_values(self, input):
        compact = {}

        for form in input:
            for key, value in form['inputs']['items'].items():
                compact[
                    'values.{}.{}'.format(form['ref'], key)
                ] = value['value']

        return compact

    def get_invalid_users(self, node_state):
        users = [
            identifier
            for identifier, actor in node_state['actors']['items'].items()
            if actor['state'] == 'invalid'
        ]

        LOGGER.debug('Invalidated node {} found users: {}'.format(
            node_state['id'],
            ', '.join(u for u in users),
        ))

        return list(map(
            lambda u: User.get_by('identifier', u),
            users
        ))

    def notify_users(self, node, pointer, channel, state):
        node_state = state['state']['items'][node.id]

        if node_state['state'] == 'invalid':
            users = self.get_invalid_users(node_state)
        else:
            users = node.get_actors(self.config, state)

        if type(users) != list:
            raise MisconfiguredProvider('Provider returned non list')

        channel.exchange_declare(
            exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
            exchange_type='direct'
        )

        notified_users = []

        for user in users:
            if not isinstance(user, User):
                raise MisconfiguredProvider(
                    'User returned by hierarchy provider is not User, '
                    'but {}'.format(type(user))
                )

            notified_users.append(user.to_json())

            user.proxy.tasks.add(pointer)

            mediums = self.get_contact_channels(user)

            for medium, params in mediums:
                channel.basic_publish(
                    exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
                    routing_key=medium,
                    body=json.dumps({**{
                        'pointer': pointer.to_json(include=['*', 'execution']),
                    }, **params}),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    ),
                )

        return notified_users

    def get_mongo(self):
        if self.mongo is None:
            client = MongoClient(self.config['MONGO_URI'])
            db = client[self.config['MONGO_DBNAME']]

            self.mongo = db

        return self.mongo

    def get_contact_channels(self, user: User):
        return [('email', {'email': user.get_x_info('email')})]

    def create_pointer(self, node, execution: Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''
        pointer = Pointer(
            node_id=node.id,
            name=node.name,
            description=node.description,
        ).save()

        pointer.proxy.execution.set(execution)

        return pointer

    def recover_step(self, message: dict):
        ''' given an execution id and a pointer from the persistent storage,
        return the asociated process node to continue its execution '''
        try:
            pointer = Pointer.get_or_exception(message['pointer_id'])
        except ModelNotFoundError:
            raise InconsistentState('Queued dead pointer')

        user = User.get_by('identifier', message.get('user_identifier'))

        if user is None:
            if message.get('user_identifier') == '__system__':
                user = User(identifier='__system__', fullname='System').save()
            else:
                raise InconsistentState('sent identifier of unexisten user')

        return (
            pointer,
            user,
            message['input'],
        )

    def cancel_execution(self, message):
        execution = Execution.get_or_exception(message['execution_id'])

        for pointer in execution.proxy.pointers.get():
            pointer.delete()

        collection = self.get_mongo()[
            self.config['EXECUTION_COLLECTION']
        ]

        collection.update_one({
            'id': execution.id,
        }, {
            '$set': {
                'status': 'cancelled',
                'finished_at': datetime.now()
            }
        })

        execution.delete()
