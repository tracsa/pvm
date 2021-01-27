from datetime import datetime
import logging

from coralillo.errors import ModelNotFoundError
from pymongo import MongoClient
import pymongo
import pika
import simplejson as json

from cacahuate.errors import CannotMove, ElementNotFound, InconsistentState
from cacahuate.errors import MisconfiguredProvider, EndOfProcess
from cacahuate.models import Execution, Pointer, User
from cacahuate.xml import Xml
from cacahuate.node import make_node, UserAttachedNode
from cacahuate.jsontypes import Map
from cacahuate.cascade import cascade_invalidate, track_next_node
from cacahuate.mongo import make_context, pointer_entry
from cacahuate.templates import render_or

LOGGER = logging.getLogger(__name__)


class Handler:
    ''' The actual process machine, it is in charge of moving the pointers
    among the graph of nodes '''

    def __init__(self, config):
        self.config = config
        self.mongo = None

    def __call__(self, channel, method, properties, body: bytes):
        ''' the main callback of cacahuate, gets called when a new message
        arrives from rabbitmq. '''
        message = json.loads(body)

        if message['command'] in self.config['COMMANDS']:
            try:
                if message['command'] == 'cancel':
                    self.cancel_execution(message)
                elif message['command'] == 'step':
                    self.step(message, channel)
                elif message['command'] == 'patch':
                    self.patch(message, channel)
            except (ModelNotFoundError, CannotMove, ElementNotFound,
                    MisconfiguredProvider, InconsistentState) as e:
                LOGGER.error(str(e))
        else:
            LOGGER.warning(
                'Unrecognized command {}'.format(message['command'])
            )

        if not self.config['RABBIT_NO_ACK']:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def step(self, message: dict, channel):
        ''' Handles deleting a pointer from the current node and creating a new
        one on the next '''
        pointer, user, input = self.recover_step(message)
        execution = pointer.proxy.execution.get()

        xml = Xml.load(self.config, execution.process_name, direct=True)
        xmliter = iter(xml)

        node = make_node(xmliter.find(
            lambda e: e.getAttribute('id') == pointer.node_id
        ), xmliter)

        # node's lifetime ends here
        self.teardown(node, pointer, user, input)
        execution.reload()

        # compute the next node in the sequence
        try:
            next_node, state = self.next(xml, node, execution)
        except EndOfProcess:
            # finish the execution
            return self.finish_execution(execution)

        self.wakeup_and_notify(next_node, execution, channel, state)

    def wakeup_and_notify(self, node, execution, channel, state):
        ''' Calls wakeup on the given node and notifies if it is a sync node
        '''
        # node's begining of life
        qdata = self.wakeup(node, execution, channel, state)

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

        state = next(self.execution_collection().find({'id': execution.id}))

        try:
            while True:
                node = node.next(
                    xml,
                    state,
                    self.get_mongo(),
                    self.config,
                )

                # refresh state because previous call might have changed it
                state = next(self.execution_collection().find({'id': execution.id}))

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

        # get currect execution context
        exc_doc = next(self.execution_collection().find({'id': execution.id}))
        context = make_context(exc_doc, self.config)

        # create a pointer in this node
        pointer = self._create_pointer(
            node.id,
            node.get_name(context),
            node.get_description(context),
            execution,
        )
        LOGGER.debug('Created pointer p:{} n:{} e:{}'.format(
            pointer.id,
            node.id,
            execution.id,
        ))

        # mark this node as ongoing
        self.execution_collection().update_one({
            'id': execution.id,
        }, {
            '$set': {
                'state.items.{}.state'.format(node.id): 'ongoing',
                'state.items.{}.name'.format(node.id): pointer.name,
                'state.items.{}.description'.format(node.id): pointer.description,
            },
        })

        # update registry about this pointer
        self.pointer_collection().insert_one(pointer_entry(
            node, pointer.name, pointer.description, execution, pointer
        ))

        # notify someone (can raise an exception
        if isinstance(node, UserAttachedNode):
            notified_users = self.notify_users(node, pointer, channel, state)
        else:
            notified_users = []

        # do some work (can raise an exception)
        if not node.is_async():
            input = node.work(self.config, state, channel, self.get_mongo())
        else:
            input = []

        # set actors to this pointer (means everything succeeded)
        self.pointer_collection().update_one({
            'id': pointer.id,
        }, {
            '$set': {
                'notified_users': notified_users,
            },
        })

        # nodes with forms are not queued
        if not node.is_async():
            return pointer, input

    def teardown(self, node, pointer, user, forms):
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
            'forms': forms,
        }

        # update pointer
        self.pointer_collection().update_one({
            'id': pointer.id,
        }, {
            '$set': {
                'state': 'finished',
                'finished_at': datetime.now(),
                'actors': Map(
                    [actor_json],
                    key=lambda a: a['user']['identifier']
                ).to_json(),
                'actor_list': [
                    {
                        'form': form['ref'],
                        'actor': user.to_json(include=[
                            '_type',
                            'fullname',
                            'identifier',
                        ]),
                    } for form in forms
                ],
            },
        })

        values = self.compact_values(forms)

        # update state
        self.execution_collection().update_one(
            {
                'id': execution.id,
                '$or': [
                    {
                        'actor_list.node': node.id,
                        'actor_list.actor.identifier': {
                            '$ne': user.identifier,
                        },
                    },
                    {
                        'actor_list.node': {
                            '$ne': node.id,
                        },
                    },
                ],
            },
            {
                '$push': {
                    'actor_list': {
                        'node': node.id,
                        'actor': user.to_json(include=[
                            '_type',
                            'fullname',
                            'identifier',
                        ]),
                    },
                },
            },
        )

        mongo_exe = self.execution_collection().find_one_and_update(
            {'id': execution.id},
            {
                '$set': {**{
                    'state.items.{node}.state'.format(node=node.id): 'valid',
                    'state.items.{node}.actors.items.{identifier}'.format(
                        node=node.id,
                        identifier=user.identifier,
                    ): actor_json,
                    'actors.{}'.format(node.id): user.identifier,
                }, **values},
            },
            return_document=pymongo.collection.ReturnDocument.AFTER,
        )

        context = make_context(mongo_exe, self.config)

        # update execution's name and description
        execution.name = render_or(
            execution.name_template,
            execution.name,
            context,
        )
        execution.description = render_or(
            execution.description_template,
            execution.description,
            context
        )
        execution.save()

        self.execution_collection().update_one(
            {'id': execution.id},
            {'$set': {
                'name': execution.name,
                'description': execution.description,
                'values._execution.0.name': execution.name,
                'values._execution.0.description': execution.description,
            }},
        )

        self.pointer_collection().update_many(
            {'execution.id': execution.id},
            {'$set': {
                'execution': execution.to_json(),
            }},
        )

        LOGGER.debug('Deleted pointer p:{} n:{} e:{}'.format(
            pointer.id,
            pointer.node_id,
            execution.id,
        ))

        pointer.delete()

    def finish_execution(self, execution):
        """ shuts down this execution and every related object """
        execution.status = 'finished'
        execution.finished_at = datetime.now()
        execution.save()

        self.execution_collection().update_one({
            'id': execution.id,
        }, {
            '$set': {
                'status': execution.status,
                'finished_at': execution.finished_at,
            }
        })

        self.pointer_collection().update_many({
            'execution.id': execution.id,
        }, {
            '$set': {
                'execution': execution.to_json(),
            }
        })

        LOGGER.debug('Finished e:{}'.format(execution.id))

        execution.delete()

    def compact_values(self, input):
        ''' Given an imput from a node create a representation that will be
        used to store the data in the 'values' key of the execution collection
        in mongodb. '''
        compact = {}

        for form in input:
            key = 'values.{}'.format(form['ref'])

            if key in compact:
                compact[key].append({
                    k: v['value'] for k, v in form['inputs']['items'].items()
                })
            else:
                compact[key] = [{
                    k: v['value'] for k, v in form['inputs']['items'].items()
                }]

        return compact

    def get_invalid_users(self, node_state):
        users = [
            identifier
            for identifier, actor in node_state['actors']['items'].items()
            if actor['state'] == 'invalid'
        ]

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

        if len(users) == 0:
            raise InconsistentState(
                'No user assigned, dead execution {}'.format(
                    pointer.proxy.execution.get().id,
                )
            )

        channel.exchange_declare(
            exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
            exchange_type='direct'
        )

        notified_users = []

        for user in users:
            notified_users.append(user.to_json())

            user.proxy.tasks.add(pointer)

            mediums = self.get_contact_channels(user)

            for medium, params in mediums:
                channel.basic_publish(
                    exchange=self.config['RABBIT_NOTIFY_EXCHANGE'],
                    routing_key=medium,
                    body=json.dumps({**{
                        'data': {
                            'pointer': pointer.to_json(
                                include=['*', 'execution']
                            ),
                            'cacahuate_url': self.config['GUI_URL'],
                        },
                    }, **params}),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    ),
                )

        LOGGER.debug('Waking up n:{} found users: {} e:{}'.format(
            node.id,
            ', '.join(u.identifier for u in users),
            pointer.proxy.execution.get().id,
        ))

        return notified_users

    def get_mongo(self):
        if self.mongo is None:
            client = MongoClient(self.config['MONGO_URI'])
            db = client[self.config['MONGO_DBNAME']]

            self.mongo = db

        return self.mongo

    def execution_collection(self):
        return self.get_mongo()[self.config['EXECUTION_COLLECTION']]

    def pointer_collection(self):
        return self.get_mongo()[self.config['POINTER_COLLECTION']]

    def get_contact_channels(self, user: User):
        return [('email', {
            'recipient': user.get_contact_info('email'),
            'subject': '[procesos] Tarea asignada',
            'template': 'assigned-task.html',
        })]

    def _create_pointer(self, node_id: str, name: str, description: str, execution: Execution):
        ''' Given a node, its process, and a specific execution of the former
        create a persistent pointer to the current execution state '''
        pointer = Pointer(
            node_id=node_id,
            name=name,
            description=description,
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

    def patch(self, message, channel):
        execution = Execution.get_or_exception(message['execution_id'])
        xml = Xml.load(self.config, execution.process_name, direct=True)

        # set nodes with pointers as unfilled, delete pointers
        updates = {}

        user = User.get_by(
            'identifier',
            message.get('user_identifier'),
        )

        if user is None:
            if message.get('user_identifier') == '__system__':
                user = User(identifier='__system__', fullname='System').save()
            else:
                raise InconsistentState('sent identifier of unexisten user')

        for pointer in execution.proxy.pointers.q():
            updates['state.items.{node}.state'.format(
                node=pointer.node_id,
            )] = 'unfilled'
            pointer.delete()
            self.pointer_collection().update_one({
                'id': pointer.id,
            }, {
                '$set': {
                    'state': 'cancelled',
                    'finished_at': datetime.now(),
                    'patch': {
                        'comment': message['comment'],
                        'inputs': message['inputs'],
                        'actor': user.to_json(include=[
                            '_type',
                            'fullname',
                            'identifier',
                        ]),
                    },
                },
            })

        self.execution_collection().update_one({
            'id': execution.id,
        }, {
            '$set': updates,
        })

        # retrieve updated state
        state = next(self.execution_collection().find({'id': execution.id}))

        state_updates = cascade_invalidate(
            xml,
            state,
            message['inputs'],
            message['comment']
        )

        # update state
        self.execution_collection().update_one({
            'id': state['id'],
        }, {
            '$set': state_updates,
        })

        # retrieve updated state
        state = next(self.execution_collection().find({'id': execution.id}))

        first_invalid_node = track_next_node(
            xml, state, self.get_mongo(), self.config
        )

        # wakeup and start execution from the found invalid node
        self.wakeup_and_notify(first_invalid_node, execution, channel, state)

    def cancel_execution(self, message):
        execution = Execution.get_or_exception(message['execution_id'])
        execution.status = 'cancelled'
        execution.finished_at = datetime.now()

        for pointer in execution.proxy.pointers.get():
            pointer.delete()

        self.execution_collection().update_one({
            'id': execution.id,
        }, {
            '$set': {
                'status': execution.status,
                'finished_at': execution.finished_at
            }
        })

        self.pointer_collection().update_many({
            'execution.id': execution.id,
            'state': 'ongoing',
        }, {
            '$set': {
                'state': 'cancelled',
                'finished_at': execution.finished_at
            }
        })

        self.pointer_collection().update_many({
            'execution.id': execution.id,
        }, {
            '$set': {
                'execution': execution.to_json(),
            }
        })

        execution.delete()
