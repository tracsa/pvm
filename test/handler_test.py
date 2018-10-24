from datetime import datetime
from unittest.mock import MagicMock
import simplejson as json
import requests

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer, User
from cacahuate.node import Action, Form
from cacahuate.xml import Xml

from .utils import make_pointer, make_user, assert_near_date, random_string


def test_recover_step(config):
    handler = Handler(config)
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
    manager = make_user('juan_manager', 'Manager')

    pointer, user, input = \
        handler.recover_step({
            'command': 'step',
            'pointer_id': ptr.id,
            'user_identifier': 'juan_manager',
            'input': [[
                'auth_form',
                [{
                    'auth': 'yes',
                }],
            ]],
        })

    assert pointer.id == pointer.id
    assert user.id == manager.id


def test_create_pointer(config):
    handler = Handler(config)

    xml = Xml.load(config, 'simple')
    xmliter = iter(xml)

    node = Action(next(xmliter), xmliter)

    exc = Execution.validate(
        process_name='simple.2018-02-19.xml',
        name='nombre',
        description='description'
    ).save()
    pointer = handler.create_pointer(node, exc)
    execution = pointer.proxy.execution.get()

    assert pointer.node_id == 'start_node'

    assert execution.process_name == 'simple.2018-02-19.xml'
    assert execution.proxy.pointers.count() == 1


def test_wakeup(config, mongo):
    ''' the first stage in a node's lifecycle '''
    # setup stuff
    handler = Handler(config)

    pointer = make_pointer('simple.2018-02-19.xml', 'start_node')
    execution = pointer.proxy.execution.get()
    juan = User(identifier='juan').save()
    manager = User(
        identifier='juan_manager',
        email='hardcoded@mailinator.com'
    ).save()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'simple').get_state(),
        'actors': {'start_node': 'juan'},
    })

    channel = MagicMock()

    # will wakeup the second node
    handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
        'user_identifier': juan.identifier,
        'input': [],
    }, channel)

    # test manager is notified
    channel.basic_publish.assert_called_once()
    channel.exchange_declare.assert_called_once()

    args = channel.basic_publish.call_args[1]

    assert args['exchange'] == config['RABBIT_NOTIFY_EXCHANGE']
    assert args['routing_key'] == 'email'
    assert json.loads(args['body']) == {
        'recipient': 'hardcoded@mailinator.com',
        'subject': '[procesos] Tarea asignada',
        'template': 'assigned-task.html',
        'data': {
            'pointer': Pointer.get_all()[0].to_json(
                include=['*', 'execution']
            ),
            'cacahuate_url': config['GUI_URL'],
        },
    }

    # pointer collection updated
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert_near_date(reg['started_at'])
    assert reg['finished_at'] is None
    assert reg['execution']['id'] == execution.id
    assert reg['node'] == {
        'id': 'mid_node',
        'type': 'action',
        'description': 'añadir información',
        'name': 'Segundo paso',
    }
    assert reg['actors'] == {
        '_type': ':map',
        'items': {},
    }
    assert reg['notified_users'] == [manager.to_json()]
    assert reg['state'] == 'ongoing'

    # execution collection updated
    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg['state']['items']['mid_node']['state'] == 'ongoing'

    # tasks where asigned
    assert manager.proxy.tasks.count() == 1

    task = manager.proxy.tasks.get()[0]

    assert isinstance(task, Pointer)
    assert task.node_id == 'mid_node'
    assert task.proxy.execution.get().id == execution.id


def test_teardown(config, mongo):
    ''' second and last stage of a node's lifecycle '''
    # test setup
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    execution = p_0.proxy.execution.get()

    User(identifier='juan').save()
    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    assert manager not in execution.proxy.actors.get()
    assert execution not in manager.proxy.activities.get()

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    state = Xml.load(config, 'simple').get_state()
    state['items']['start_node']['state'] = 'valid'

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
        'values': {},
        'actors': {
            'start_node': 'juan',
        },
    })

    mongo[config["POINTER_COLLECTION"]].insert_one({
        'id': p_0.id,
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': p_0.node_id,
        },
        'actors': {
            '_type': ':map',
            'items': {},
        },
    })

    channel = MagicMock()

    # will teardown mid_node
    handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'user_identifier': manager.identifier,
        'input': [Form.state_json('mid_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'yes',
                'name': 'data',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(p_0.id) is None

    assert Pointer.count() == 1
    assert Pointer.get_all()[0].node_id == 'final_node'

    # mongo has a registry
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert_near_date(reg['finished_at'])
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == p_0.node_id
    assert reg['actors'] == {
        '_type': ':map',
        'items': {
            'manager': {
                '_type': 'actor',
                'state': 'valid',
                'user': {
                    '_type': 'user',
                    'identifier': 'manager',
                    'fullname': None,
                },
                'forms': [Form.state_json('mid_form', [
                    {
                        '_type': 'field',
                        'state': 'valid',
                        'value': 'yes',
                        'name': 'data',
                    },
                ])],
            },
        },
    }

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0

    # state
    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg['state'] == {
        '_type': ':sorted_map',
        'items': {
            'start_node': {
                '_type': 'node',
                'type': 'action',
                'id': 'start_node',
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {},
                },
                'milestone': False,
                'name': 'Primer paso',
                'description': 'Resolver una tarea',
            },

            'mid_node': {
                '_type': 'node',
                'type': 'action',
                'id': 'mid_node',
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {
                        'manager': {
                            '_type': 'actor',
                            'state': 'valid',
                            'user': {
                                '_type': 'user',
                                'identifier': 'manager',
                                'fullname': None,
                            },
                            'forms': [Form.state_json('mid_form', [
                                {
                                    '_type': 'field',
                                    'state': 'valid',
                                    'value': 'yes',
                                    'name': 'data',
                                },
                            ])],
                        },
                    },
                },
                'milestone': False,
                'name': 'Segundo paso',
                'description': 'añadir información',
            },

            'final_node': {
                '_type': 'node',
                'type': 'action',
                'id': 'final_node',
                'state': 'ongoing',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {},
                },
                'milestone': False,
                'name': '',
                'description': '',
            },
        },
        'item_order': [
            'start_node',
            'mid_node',
            'final_node',
        ],
    }

    assert reg['values'] == {
        'mid_form': {
            'data': 'yes',
        },
    }

    assert reg['actors'] == {
        'start_node': 'juan',
        'mid_node': 'manager',
    }

    assert manager in execution.proxy.actors
    assert execution in manager.proxy.activities


def test_finish_execution(config, mongo):
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'manager')
    execution = p_0.proxy.execution.get()
    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'status': 'ongoing',
        'id': execution.id
    })

    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())
    assert execution.id == reg['id']

    handler.finish_execution(execution)

    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg['status'] == 'finished'
    assert_near_date(reg['finished_at'])


def test_call_handler_delete_process(config, mongo):
    handler = Handler(config)
    channel = MagicMock()
    method = {'delivery_tag': True}
    properties = ""
    pointer = make_pointer('simple.2018-02-19.xml', 'requester')
    execution_id = pointer.proxy.execution.get().id
    body = '{"command":"cancel", "execution_id":"%s", "pointer_id":"%s"}'\
        % (execution_id, pointer.id)

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'status': 'ongoing',
        'id': execution_id
    })

    handler(channel, method, properties, body)

    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg['id'] == execution_id
    assert reg['status'] == "cancelled"
    assert_near_date(reg['finished_at'])

    assert Execution.count() == 0
    assert Pointer.count() == 0


def test_approve(config, mongo):
    ''' tests that a validation node can go forward on approval '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    channel = MagicMock()

    mongo[config["POINTER_COLLECTION"]].insert_one({
        'id': ptr.id,
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': ptr.proxy.execution.get().id,
        },
        'node': {
            'id': 'approval_node',
        },
        'actors': {
            '_type': ':map',
            'items': {},
        },
    })

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'validation.2018-05-09').get_state(),
        'actors': {
            'start_node': 'juan',
        },
    })

    # thing to test
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'accept',
            },
            {
                'name': 'comment',
                'value': 'I like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0.task',
                }],
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'final_node'

    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert_near_date(reg['finished_at'])
    assert reg['execution']['id'] == ptr.execution
    assert reg['node']['id'] == 'approval_node'
    assert reg['actors'] == {
        '_type': ':map',
        'items': {
            'juan': {
                '_type': 'actor',
                'state': 'valid',
                'user': {
                    '_type': 'user',
                    'identifier': 'juan',
                    'fullname': 'Juan',
                },
                'forms': [Form.state_json('approval_node', [
                    {
                        'name': 'response',
                        'name': 'response',
                        'value': 'accept',
                    },
                    {
                        'name': 'comment',
                        'name': 'comment',
                        'value': 'I like it',
                    },
                    {
                        'name': 'inputs',
                        'name': 'inputs',
                        'value': [{
                            'ref': 'start_node.juan.0.task',
                        }],
                    },
                ])],
            },
        },
    }


def test_reject(config, mongo):
    ''' tests that a rejection moves the pointer to a backward position '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()

    mongo[config["POINTER_COLLECTION"]].insert_one({
        'id': ptr.id,
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': 'approval_node',
        },
        'actors': {
            '_type': ':map',
            'items': {},
        },
    })

    state = Xml.load(config, 'validation.2018-05-09').get_state()

    state['items']['start_node']['state'] = 'valid'
    state['items']['start_node']['actors']['items']['juan'] = {
        '_type': 'actor',
        'state': 'valid',
        'user': {
            '_type': 'user',
            'identifier': 'juan',
            'fullname': 'Juan',
        },
        'forms': [Form.state_json('work', [
            {
                'name': 'task',
                '_type': 'field',
                'state': 'valid',
                'value': '2',
            },
        ])],
    }

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
    })

    # will teardown the approval node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'reject',
            },
            {
                'name': 'comment',
                'value': 'I do not like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:work.task',
                }],
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'start_node'

    assert new_ptr in user.proxy.tasks

    # data is invalidated
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    del state['_id']

    assert state == {
        '_type': 'execution',
        'id': execution.id,
        'state': {
            '_type': ':sorted_map',
            'items': {
                'start_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'start_node',
                    'state': 'ongoing',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('work', [
                                    {
                                        'name': 'task',
                                        '_type': 'field',
                                        'state': 'invalid',
                                        'value': '2',
                                    },
                                ], state='invalid')],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Primer paso',
                    'description': 'Resolver una tarea',
                },

                'approval_node': {
                    '_type': 'node',
                    'type': 'validation',
                    'id': 'approval_node',
                    'state': 'invalid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('approval_node', [
                                    {
                                        'name': 'response',
                                        'state': 'invalid',
                                        'value': 'reject',
                                    },
                                    {
                                        'name': 'comment',
                                        'value': 'I do not like it',
                                    },
                                    {
                                        'name': 'inputs',
                                        'value': [{
                                            'ref': 'start_node.'
                                                   'juan.0:work.task',
                                        }],
                                    },
                                ], state='invalid')],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Aprobación gerente reserva',
                    'description': 'aprobar reserva',
                },

                'final_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'final_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },
            },
            'item_order': ['start_node', 'approval_node', 'final_node'],
        },
        'values': {
            'approval_node': {
                'comment': 'I do not like it',
                'response': 'reject',
                'inputs': [{'ref': 'start_node.juan.0:work.task'}],
            },
        },
        'actors': {
            'approval_node': 'juan',
        },
    }

    # mongo has the data
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == ptr.execution
    assert reg['node']['id'] == 'approval_node'
    assert reg['actors'] == {
        '_type': ':map',
        'items': {
            'juan': {
                '_type': 'actor',
                'forms': [Form.state_json('approval_node', [
                    {
                        'name': 'response',
                        'value': 'reject',
                    },
                    {
                        'name': 'comment',
                        'value': 'I do not like it',
                    },
                    {
                        'name': 'inputs',
                        'value': [{
                            'ref': 'start_node.juan.0:work.task',
                        }],
                    },
                ])],
                'state': 'valid',
                'user': {
                    '_type': 'user',
                    'identifier': 'juan',
                    'fullname': 'Juan',
                },
            },
        },
    }


def test_reject_with_dependencies(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation-reloaded.2018-05-17.xml', 'node1')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'validation-reloaded').get_state(),
    })

    # first call to node1
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'task',
                'value': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # first call to node2
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form2', [
            {
                'name': 'task',
                'value': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node3'

    # first call to node3
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form3', [
            {
                'name': 'task',
                'value': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # first call to validation
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('node4', [
            {
                'name': 'response',
                'value': 'reject',
            },
            {
                'name': 'comment',
                'value': 'I do not like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'node1.juan.0:form1.task',
                }],
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node1'

    # second call to node1
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'task',
                'value': '2',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # second call to node2
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form2', [
            {
                'name': 'task',
                'value': '2',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # second call to validation
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('node4', [
            {
                'name': 'response',
                'value': 'accept',
            },
            {
                'name': 'comment',
                'value': 'I like it',
            },
            {
                'name': 'inputs',
                'value': None,
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node5'

    # first call to last node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form5', [
            {
                'name': 'task',
                'value': '1',
            },
        ])],
    }, channel)
    assert Pointer.get_all() == []

    # state is coherent
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    del state['_id']
    del state['finished_at']

    assert state == {
        '_type': 'execution',
        'id': execution.id,
        'state': {
            '_type': ':sorted_map',
            'items': {
                'node1': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'node1',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('form1', [
                                    {
                                        'name': 'task',
                                        'value': '2',
                                    },
                                ])],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Primer paso',
                    'description': 'información original',
                },

                'node2': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'node2',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('form2', [
                                    {
                                        'name': 'task',
                                        'value': '2',
                                    },
                                ])],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Segundo paso',
                    'description': 'depender de la info',
                },

                'node3': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'node3',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('form3', [
                                    {
                                        'name': 'task',
                                        'value': '1',
                                    },
                                ])],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Tercer paso',
                    'description': 'no depender de nada',
                },

                'node4': {
                    '_type': 'node',
                    'type': 'validation',
                    'id': 'node4',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('node4', [
                                    {
                                        'name': 'response',
                                        'value': 'accept',
                                    },
                                    {
                                        'name': 'comment',
                                        'value': 'I like it',
                                    },
                                    {
                                        'name': 'inputs',
                                        'value': None,
                                    },
                                ])],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Cuarto paso',
                    'description': 'validar',
                },

                'node5': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'node5',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json('form5', [
                                    {
                                        'name': 'task',
                                        'value': '1',
                                    },
                                ])],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Quinto paso',
                    'description': 'terminar',
                },
            },
            'item_order': ['node1', 'node2', 'node3', 'node4', 'node5'],
        },
        'status': 'finished',
        'values': {
            'node4': {
                'comment': 'I like it',
                'inputs': None,
                'response': 'accept',
            },
            'form1': {'task': '2'},
            'form2': {'task': '2'},
            'form3': {'task': '1'},
            'form5': {'task': '1'},
        },
        'actors': {
            'node1': 'juan',
            'node2': 'juan',
            'node3': 'juan',
            'node4': 'juan',
            'node5': 'juan',
        },
    }


def test_patch_invalidate(config, mongo):
    ''' patch that only invalidates '''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'exit_request').get_state(),
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('exit_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'want to pee',
                'name': 'reason',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'manager'

    # manager says yes
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('auth_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'yes',
                'name': 'auth',
            },
        ])],
    }, channel)
    security_ptr = execution.proxy.pointers.get()[0]
    assert security_ptr.node_id == 'security'

    # patch request happens
    channel = MagicMock()
    handler.patch({
        'command': 'patch',
        'execution_id': execution.id,
        'comment': 'pee is not a valid reason',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
        }],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]

    # pointer is in the first node
    assert ptr.node_id == 'requester'

    # nodes with pointers are marked as unfilled or invalid in execution state
    exc_state = mongo[config['EXECUTION_COLLECTION']].find_one({
        'id': execution.id,
    })

    assert exc_state['state']['items']['security']['state'] == 'unfilled'

    # dependent information is invalidated
    assert exc_state['state']['items']['manager']['state'] == 'invalid'

    # entries in pointer collection get a state of cancelled by patch request
    security_pointer_state = mongo[config['POINTER_COLLECTION']].find_one({
        'id': security_ptr.id,
    })

    assert security_pointer_state['state'] == 'cancelled'


def test_patch_set_value(config, mongo):
    ''' patch and set new data '''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'exit_request').get_state(),
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('exit_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'want to pee',
                'name': 'reason',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'manager'

    # manager says yes
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('auth_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'yes',
                'name': 'auth',
            },
        ])],
    }, channel)
    security_ptr = execution.proxy.pointers.get()[0]
    assert security_ptr.node_id == 'security'

    # patch request happens
    channel = MagicMock()
    handler.patch({
        'command': 'patch',
        'execution_id': execution.id,
        'comment': 'pee is not a valid reason',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
            'value': 'am hungry',
            'value_caption': 'am hungry',
        }],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]

    # pointer is in the manager's node
    assert ptr.node_id == 'manager'

    # nodes with pointers are marked as unfilled or invalid in execution state
    exc_state = mongo[config['EXECUTION_COLLECTION']].find_one({
        'id': execution.id,
    })

    # values sent are set
    actor = exc_state['state']['items']['requester']['actors']['items']['juan']
    _input = actor['forms'][0]['inputs']['items']['reason']

    assert _input['value'] == 'am hungry'
    assert _input['value_caption'] == 'am hungry'


def test_resistance_unexisteng_hierarchy_backend(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start_node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, 'wrong').get_state(),
    })

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': {},
    }))


def test_resistance_hierarchy_return(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start_node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, 'wrong').get_state(),
    })

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': {},
    }))


def test_resistance_hierarchy_item(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start_node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, 'wrong').get_state(),
    })

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': {},
    }))


def test_resistance_node_not_found(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start_node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, 'wrong').get_state(),
    })

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': {},
    }))


def test_resistance_dead_pointer(config):
    handler = Handler(config)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': 'nones',
    }))


def test_true_condition_node(config, mongo):
    ''' conditional node will be executed if its condition is true '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'condition').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('mistery', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'abrete sésamo',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition1'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition1', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'mistical_node'


def test_false_condition_node(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'condition').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('mistery', [
            {
                'name': 'password',
                'type': 'text',
                'value': '123456',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition1'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition1', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition2'


def test_anidated_conditions(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('anidated-conditions.2018-05-17.xml', 'a')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'anidated-conditions').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('a', [
            {
                'name': 'a',
                'value': '1',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'outer'

    # rabbit called
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('outer', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'b'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('b', [
            {
                'name': 'b',
                'value': '-1',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'inner1'

    # rabbit called
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('inner1', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'f'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('f', [
            {
                'name': 'f',
                'value': '-1',
            },
        ])],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'g'


def test_ifelifelse_if(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'incorrect!',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action01'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_ifelifelse_elif(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'hocus pocus',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action02'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_ifelifelse_else(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'cuca',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'else01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('else01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action03'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_exit_interaction(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit.2018-05-03.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'exit').get_state(),
    })

    # first node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id

    args = channel.basic_publish.call_args[1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }

    # exit node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }, channel)

    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0

    # state is coherent
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    del state['_id']
    del state['finished_at']

    assert state == {
        '_type': 'execution',
        'id': execution.id,
        'state': {
            '_type': ':sorted_map',
            'items': {
                'start_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'start_node',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },

                'exit': {
                    '_type': 'node',
                    'type': 'exit',
                    'id': 'exit',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            '__system__': {
                                '_type': 'actor',
                                'forms': [],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': '__system__',
                                    'fullname': 'System',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Exit exit',
                    'description': 'Exit exit',
                },

                'final_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'final_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },
            },
            'item_order': ['start_node', 'exit', 'final_node'],
        },
        'status': 'finished',
        'actors': {
            'exit': '__system__',
            'start_node': 'juan',
        },
    }


def test_call_node(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('call.2018-05-18.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'call').get_state(),
    })

    # teardown of first node and wakeup of call node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('start_form', [
            {
                'name': 'data',
                'name': 'data',
                'value': value,
            },
        ])],
    }, channel)
    assert Pointer.get(ptr.id) is None
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'call'

    new_ptr = next(Pointer.q().filter(node_id='start_node'))

    # aditional rabbit call for new process
    args = channel.basic_publish.call_args_list[0][1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': new_ptr.id,
        'user_identifier': '__system__',
        'input': [Form.state_json('start_form', [
            {
                'label': 'Info',
                'name': 'data',
                'state': 'valid',
                'type': 'text',
                'value': value,
                'value_caption': value,
                'hidden': False,
            },
        ])],
    }

    # normal rabbit call
    args = channel.basic_publish.call_args_list[1][1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }

    # mongo log registry created for new process
    reg = next(mongo[config["POINTER_COLLECTION"]].find({
        'id': new_ptr.id,
    }))
    assert reg['node']['id'] == 'start_node'

    # mongo execution registry created for new process
    reg = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': new_ptr.proxy.execution.get().id,
    }))
    assert reg['name'] == 'Simplest process ever started with: ' + value

    # teardown of the call node and end of first execution
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }, channel)

    # old execution is gone, new is here
    assert Execution.get(execution.id) is None
    assert Pointer.get(ptr.id) is None
    execution = Execution.get_all()[0]
    assert execution.process_name == 'simple.2018-02-19.xml'


def test_handle_request_node(config, mocker, mongo):
    class ResponseMock:
        status_code = 200
        text = 'request response'

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new=mock
    )

    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('request.2018-05-18.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'request').get_state(),
    })

    # teardown of first node and wakeup of request node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('request', [
            {
                'name': 'data',
                'value': value
            },
        ])],
    }, channel)
    assert Pointer.get(ptr.id) is None
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'request_node'

    # assert requests is called
    requests.request.assert_called_once()
    args, kwargs = requests.request.call_args

    assert args[0] == 'POST'
    assert args[1] == 'http://localhost/mirror?data=' + value

    assert kwargs['data'] == '{"data":"' + value + '"}'
    assert kwargs['headers'] == {
        'content-type': 'application/json',
        'x-url-data': value,
    }

    # aditional rabbit call for new process
    args = channel.basic_publish.call_args_list[0][1]

    expected_inputs = [Form.state_json('request_node', [
        {
            'name': 'status_code',
            'state': 'valid',
            'type': 'int',
            'value': 200,
            'value_caption': '200',
            'hidden': False,
            'label': 'Status Code',
        },
        {
            'name': 'raw_response',
            'state': 'valid',
            'type': 'text',
            'value': 'request response',
            'value_caption': 'request response',
            'hidden': False,
            'label': 'Response',
        },
    ])]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }, channel)

    state = mongo[config["EXECUTION_COLLECTION"]].find_one({
        'id': execution.id,
    })

    assert state['state']['items']['request_node'] == {
        '_type': 'node',
        'type': 'request',
        'id': 'request_node',
        'comment': '',
        'state': 'valid',
        'actors': {
            '_type': ':map',
            'items': {
                '__system__': {
                    '_type': 'actor',
                    'state': 'valid',
                    'user': {
                        '_type': 'user',
                        'fullname': 'System',
                        'identifier': '__system__',
                    },
                    'forms': expected_inputs,
                },
            },
        },
        'milestone': False,
        'name': 'Request request_node',
        'description': 'Request request_node',
    }


def test_invalidate_all_nodes(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('all-nodes-invalidated.2018-05-24.xml', 'start_node')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'all-nodes-invalidated').get_state(),
    })

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('work', [
            {
                'name': 'task',
                'value': '2',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'request_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.call(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'call_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.call(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'if_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.call(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'validation_node'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('validation_node', [
            {
                'name': 'response',
                'value': 'reject',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:work.task',
                }],
            },
            {
                'name': 'comment',
                'value': '',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'start_node'
    args = channel.basic_publish.call_args[1]
