from datetime import datetime
from unittest.mock import MagicMock
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.node import Form
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user, assert_near_date


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
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        },
    })

    # thing to test
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'accept',
                'value_caption': 'accept',
            },
            {
                'name': 'comment',
                'value': 'I like it',
                'value_caption': 'I like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0.task',
                }],
                'value_caption': '',
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
                        'value_caption': 'accept',
                    },
                    {
                        'name': 'comment',
                        'name': 'comment',
                        'value': 'I like it',
                        'value_caption': 'I like it',
                    },
                    {
                        'name': 'inputs',
                        'name': 'inputs',
                        'value': [{
                            'ref': 'start_node.juan.0.task',
                        }],
                        'value_caption': '',
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
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        },
    })

    # will teardown the approval node
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'reject',
                'value_caption': 'reject',
            },
            {
                'name': 'comment',
                'value': 'I do not like it',
                'value_caption': 'I do not like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:work.task',
                }],
                'value_caption': '',
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
        'name': '',
        'description': '',
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
                                        'value_caption': 'reject',
                                    },
                                    {
                                        'name': 'comment',
                                        'value': 'I do not like it',
                                        'value_caption': 'I do not like it',
                                    },
                                    {
                                        'name': 'inputs',
                                        'value': [{
                                            'ref': 'start_node.'
                                                   'juan.0:work.task',
                                        }],
                                        'value_caption': '',
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
            '_execution': [{
                'name': '',
                'description': '',
            }],
            'approval_node': [{
                'comment': 'I do not like it',
                'response': 'reject',
                'inputs': [{'ref': 'start_node.juan.0:work.task'}],
            }],
        },
        'actors': {
            'approval_node': 'juan',
        },
        'actor_list': [{
            'node': 'approval_node',
            'identifier': 'juan',
        }],
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
                        'value_caption': 'reject',
                    },
                    {
                        'name': 'comment',
                        'value': 'I do not like it',
                        'value_caption': 'I do not like it',
                    },
                    {
                        'name': 'inputs',
                        'value': [{
                            'ref': 'start_node.juan.0:work.task',
                        }],
                        'value_caption': '',
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
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        },
    })

    # first call to node1
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'task',
                'value': '1',
                'value_caption': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # first call to node2
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form2', [
            {
                'name': 'task',
                'value': '1',
                'value_caption': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node3'

    # first call to node3
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form3', [
            {
                'name': 'task',
                'value': '1',
                'value_caption': '1',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # first call to validation
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('node4', [
            {
                'name': 'response',
                'value': 'reject',
                'value_caption': 'reject',
            },
            {
                'name': 'comment',
                'value': 'I do not like it',
                'value_caption': 'I do not like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'node1.juan.0:form1.task',
                }],
                'value_caption': '',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node1'

    # second call to node1
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'task',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # second call to node2
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form2', [
            {
                'name': 'task',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # second call to validation
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('node4', [
            {
                'name': 'response',
                'value': 'accept',
                'value_caption': 'accept',
            },
            {
                'name': 'comment',
                'value': 'I like it',
                'value_caption': 'I like it',
            },
            {
                'name': 'inputs',
                'value': None,
                'value_caption': 'None',
            },
        ])],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node5'

    # first call to last node
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form5', [
            {
                'name': 'task',
                'value': '1',
                'value_caption': '1',
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
        'name': '',
        'description': '',
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
                                        'value_caption': '2',
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
                                        'value_caption': '2',
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
                                        'value_caption': '1',
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
                                        'value_caption': 'accept',
                                    },
                                    {
                                        'name': 'comment',
                                        'value': 'I like it',
                                        'value_caption': 'I like it',
                                    },
                                    {
                                        'name': 'inputs',
                                        'value': None,
                                        'value_caption': 'None',
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
                                        'value_caption': '1',
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
            '_execution': [{
                'name': '',
                'description': '',
            }],
            'node4': [{
                'comment': 'I like it',
                'inputs': None,
                'response': 'accept',
            }],
            'form1': [{'task': '2'}],
            'form2': [{'task': '2'}],
            'form3': [{'task': '1'}],
            'form5': [{'task': '1'}],
        },
        'actors': {
            'node1': 'juan',
            'node2': 'juan',
            'node3': 'juan',
            'node4': 'juan',
            'node5': 'juan',
        },
        'actor_list': [
            {
                'node': 'node1',
                'identifier': 'juan',
            },
            {
                'node': 'node2',
                'identifier': 'juan',
            },
            {
                'node': 'node3',
                'identifier': 'juan',
            },
            {
                'node': 'node4',
                'identifier': 'juan',
            },
            {
                'node': 'node5',
                'identifier': 'juan',
            },
        ],
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
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('work', [
            {
                'name': 'task',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'request_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.step(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'call_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.step(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'if_node'
    args = channel.basic_publish.call_args[1]

    channel = MagicMock()
    handler.step(json.loads(args['body']), channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'validation_node'

    channel = MagicMock()
    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('validation_node', [
            {
                'name': 'response',
                'value': 'reject',
                'value_caption': 'reject',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:work.task',
                }],
                'value_caption': '',
            },
            {
                'name': 'comment',
                'value': '',
                'value_caption': '',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'start_node'
    args = channel.basic_publish.call_args[1]
