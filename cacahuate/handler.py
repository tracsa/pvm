from case_conversion import pascalcase
from coralillo.errors import ModelNotFoundError
from datetime import datetime
from importlib import import_module
from pymongo import MongoClient
import simplejson as json
import pika
import pymongo

from cacahuate.errors import CannotMove, ElementNotFound, InconsistentState, \
    MisconfiguredProvider
from cacahuate.logger import log
from cacahuate.models import Execution, Pointer, Questionaire, Activity, User
from cacahuate.node import make_node, Node
from cacahuate.xml import Xml, resolve_params, get_node_info
from cacahuate.auth.base import BaseUser
from cacahuate.utils import user_import


class Handler:
    ''' The actual process machine, it is in charge of moving the pointers
    among the graph of nodes '''

    def __init__(self, config):
        self.config = config
        self.mongo = None

    def __call__(self, channel, method, properties, body: bytes):
        ''' the main callback of cacahuate '''
        message = self.parse_message(body)

        if message['command'] == 'cancel':
            self.cancel_execution(message)
        elif message['command'] == 'step':
            try:
                self.call(message, channel)
            except (ModelNotFoundError, CannotMove, ElementNotFound,
                    MisconfiguredProvider, InconsistentState
                    ) as e:
                log.error(str(e))
        else:
            log.warning('Unrecognized command {}'.format(message['command']))

        if not self.config['RABBIT_NO_ACK']:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def call(self, message: dict, channel):
        execution, pointer, xml, cur_node, actor = self.recover_step(message)

        to_queue = []  # pointers to be sent to the queue

        # node's lifetime ends here
        self.teardown(pointer, actor)
        next_nodes = cur_node.next(xml, execution)

        for is_backwards, node in next_nodes:
            # Nodes that come from the past have special threatment
            if is_backwards:
                self.recover_state(node, execution)

            # node's begining of life
            pointer = self.wakeup(node, execution, channel)

            # async nodes don't return theirs pointers so they are not queued
            if pointer:
                to_queue.append(pointer)

        if execution.proxy.pointers.count() == 0:
            self.finish_execution(execution)

        channel.queue_declare(
            queue=self.config['RABBIT_QUEUE'],
            durable=True
        )

        for pointer in to_queue:
            channel.basic_publish(
                exchange='',
                routing_key=self.config['RABBIT_QUEUE'],
                body=json.dumps({
                    'command': 'step',
                    'pointer_id': pointer.id,
                }),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
            )

    def wakeup(self, node, execution, channel):
        ''' Waking up a node often means to notify someone or something about
        the execution, this is the first step in node's lifecycle '''

        # create a pointer in this node
        pointer = self.create_pointer(node, execution)
        log.debug('Created pointer p:{} n:{} e:{}'.format(
            pointer.id,
            node.element.getAttribute('id'),
            execution.id,
        ))
        is_async = len(node.element.getElementsByTagName('form-array')) > 0

        # notify someone
        notified_users = self.notify_users(node, pointer, channel)

        # update registry about this pointer
        collection = self.get_mongo()[self.config['MONGO_HISTORY_COLLECTION']]

        collection.insert_one({
            'started_at': datetime.now(),
            'finished_at': None,
            'execution': {
                'id': execution.id,
                'name': execution.name,
                'description': execution.description,
            },
            'node': {**{
                'id': node.element.getAttribute('id'),
            }, **get_node_info(node.element)},
            'notified_users': notified_users,
            'actors': [],
            'state': execution.get_state(),
        })

        # nodes with forms are not queued
        if not is_async:
            return pointer

    def teardown(self, pointer, actor):
        ''' finishes the node's lifecycle '''
        collection = self.get_mongo()[self.config['MONGO_HISTORY_COLLECTION']]

        update_query = {
            '$set': {
                'finished_at': datetime.now(),
            },
        }

        if actor is not None:
            update_query['$push'] = {
                'actors': actor,
            }

        collection.update_one({
            'execution.id': pointer.proxy.execution.get().id,
            'node.id': pointer.node_id,
        }, update_query)

        log.debug('Deleted pointer p:{} n:{} e:{}'.format(
            pointer.id,
            pointer.node_id,
            pointer.proxy.execution.get().id,
        ))

        pointer.delete()

    def finish_execution(self, execution):
        """ shuts down this execution and every related object """
        self.delete_related_objects(execution)

        mongo = self.get_mongo()
        collection = mongo[self.config['MONGO_EXECUTION_COLLECTION']]
        collection.update_one({
            'id': execution.id
        }, {
            '$set': {
                'status': 'finished',
                'finished_at': datetime.now()
            }
        })

        log.debug('Finished e:{}'.format(execution.id))

        execution.delete()

    def delete_related_objects(self, execution):
        for activity in execution.proxy.actors.get():
            activity.delete()

        for form in execution.proxy.forms.get():
            form.delete()

    def recover_state(self, node, execution):
        ''' recovers the lost state '''
        self.delete_related_objects(execution)

        mongo = self.get_mongo()

        # finds most recent registry for this node
        collection = mongo[self.config['MONGO_HISTORY_COLLECTION']]
        prev_state = next(collection.find({
            'execution_id': execution.id,
            'node_id': node.element.getAttribute('id'),
        }).sort([
            ('started_at', pymongo.DESCENDING)
        ]))

        # restores froms and actors from that time
        for form_data in prev_state['state']['forms']:
            q = Questionaire(**form_data).save()
            q.proxy.execution.set(execution)

        for act_data in prev_state['state']['actors']:
            a = Activity(**act_data).save()
            a.proxy.execution.set(execution)
            a.proxy.user.set(User.get(act_data['user_id']))

        # sets state in mongo
        collection = mongo[self.config['MONGO_EXECUTION_COLLECTION']]
        collection.update_one({
            'id': execution.id,
        }, {
            '$set': {
                'state': execution.get_state(),
            },
        })

    def notify_users(self, node, pointer, channel):
        filter_q = node.element.getElementsByTagName('auth-filter')

        if len(filter_q) == 0:
            return []

        filter_node = filter_q[0]

        backend = filter_node.getAttribute('backend')

        HiPro = user_import(
            backend,
            'HierarchyProvider',
            self.config['HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
        )

        hierarchy_provider = HiPro(self.config)
        husers = hierarchy_provider.find_users(
            **resolve_params(filter_node, pointer.proxy.execution.get())
        )

        if type(husers) != list:
            raise MisconfiguredProvider('Provider returned non list')

        channel.exchange_declare(
            exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
            exchange_type='direct'
        )

        notified_users = []

        for huser in husers:
            if not isinstance(huser, BaseUser):
                raise MisconfiguredProvider(
                    'User returned by hierarchy provider is not BaseUser, '
                    'but {}'.format(type(huser))
                )
            user = huser.get_user()
            notified_users.append(user.to_json())

            user.proxy.tasks.add(pointer)

            mediums = self.get_contact_channels(huser)

            for medium, params in mediums:
                log.debug('Notified user {} via {} about n:{} e:{}'.format(
                    user.identifier,
                    medium,
                    node.element.getAttribute('id'),
                    pointer.proxy.execution.get().id,
                ))
                channel.basic_publish(
                    exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
                    routing_key=medium,
                    body=json.dumps({**{
                        'pointer': pointer.to_json(embed=['execution']),
                    }, **params}),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    ),
                )

        return notified_users

    def parse_message(self, body: bytes):
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

    def get_mongo(self):
        if self.mongo is None:
            client = MongoClient()
            db = client[self.config['MONGO_DBNAME']]

            self.mongo = db

        return self.mongo

    def get_contact_channels(self, user: BaseUser):
        return [('email', {'email': user.get_x_info('email')})]

    def create_pointer(self, node: Node, execution: Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''
        node_info = node.element.getElementsByTagName('node-info')

        pointer = Pointer(
            node_id=node.element.getAttribute('id'),
            **get_node_info(node.element),
        ).save()

        pointer.proxy.execution.set(execution)

        return pointer

    def recover_step(self, message: dict):
        ''' given an execution id and a pointer from the persistent storage,
        return the asociated process node to continue its execution '''
        if 'pointer_id' not in message:
            raise KeyError('Requested step without pointer id')

        pointer = Pointer.get_or_exception(message['pointer_id'])
        execution = pointer.proxy.execution.get()

        if execution is None:
            raise InconsistentState('Found an orphan pointer')

        xml = Xml.load(self.config, execution.process_name)

        assert execution.process_name == xml.filename, 'Inconsistent pointer'

        point = xml.find(
            lambda e: e.getAttribute('id') == pointer.node_id
        )

        return (
            execution,
            pointer,
            xml,
            make_node(point),
            message.get('actor'),
        )

    def cancel_execution(self, message):
        execution = Execution.get_or_exception(message['execution_id'])

        for pointer in execution.proxy.pointers.get():
            pointer.delete()

        for activity in execution.proxy.actors.get():
            activity.delete()

        for form in execution.proxy.forms.get():
            form.delete()

        collection = self.get_mongo()[
            self.config['MONGO_EXECUTION_COLLECTION']
        ]

        collection.update_one({
            'execution_id': execution.id
        }, {
            '$set': {
                'status': 'cancelled',
                'finished_at': datetime.now()
            }
        })

        execution.delete()
