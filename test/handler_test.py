from datetime import datetime
from unittest.mock import MagicMock
from xml.dom.minidom import Document
import pika
import pytest
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer, User
from cacahuate.node import Action
from cacahuate.xml import Xml

from .utils import make_pointer, make_user, assert_near_date


def test_recover_step(config):
    handler = Handler(config)
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    exc = ptr.proxy.execution.get()
    manager = make_user('juan_manager', 'Manager')

    pointer, user, input = \
        handler.recover_step({
            'command': 'step',
            'pointer_id': ptr.id,
            'user_identifier': 'juan_manager',
            'input': [[
                'auth-form',
                [{
                    'auth': 'yes',
                }],
            ]],
        })

    assert pointer.id == pointer.id
    assert user.id == manager.id


def test_create_pointer(config):
    handler = Handler(config)

    ele = Document().createElement('node')
    ele.setAttribute('class', 'simple')
    ele.setAttribute('id', 'chubaca')

    node_name = Document().createTextNode('nombre')
    node_desc = Document().createTextNode('descripción')

    # Build node structure
    node_info_el = Document().createElement('node-info')
    node_name_el = Document().createElement('name')
    node_desc_el = Document().createElement('description')

    node_name_el.appendChild(node_name)
    node_info_el.appendChild(node_name_el)

    node_desc_el.appendChild(node_desc)
    node_info_el.appendChild(node_desc_el)

    ele.appendChild(node_info_el)

    node = Action(ele)
    exc = Execution.validate(
        process_name='simple.2018-02-19.xml',
        name='nombre',
        description='description'
    ).save()
    pointer = handler.create_pointer(node, exc)
    execution = pointer.proxy.execution.get()

    assert pointer.node_id == 'chubaca'

    assert execution.process_name == 'simple.2018-02-19.xml'
    assert execution.proxy.pointers.count() == 1


def test_wakeup(config, mongo):
    ''' the first stage in a node's lifecycle '''
    # setup stuff
    handler = Handler(config)

    pointer = make_pointer('simple.2018-02-19.xml', 'start-node')
    execution = pointer.proxy.execution.get()
    juan = User(identifier='juan').save()
    manager = User(
        identifier='juan_manager',
        email='hardcoded@mailinator.com'
    ).save()

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'simple').get_state(),
    })

    channel = MagicMock()

    # this is what we test
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
        'email': 'hardcoded@mailinator.com',
        'pointer': Pointer.get_all()[0].to_json(include=['*', 'execution']),
    }

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert_near_date(reg['started_at'])
    assert reg['finished_at'] is None
    assert reg['execution']['id'] == execution.id
    assert reg['node'] == {
        'id': 'mid-node',
        'type': 'action',
        'description': 'añadir información',
        'name': 'Segundo paso',
    }
    assert reg['actors'] == {
        '_type': ':map',
        'items': {},
    }
    assert reg['notified_users'] == [manager.to_json()]
    with pytest.raises(KeyError):
        reg['state']

    # tasks where asigned
    assert manager.proxy.tasks.count() == 1

    task = manager.proxy.tasks.get()[0]

    assert isinstance(task, Pointer)
    assert task.node_id == 'mid-node'
    assert task.proxy.execution.get().id == execution.id


def test_teardown(config, mongo):
    ''' second and last stage of a node's lifecycle '''
    # test setup
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'mid-node')
    execution = p_0.proxy.execution.get()

    juan = User(identifier='juan').save()
    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    assert manager not in execution.proxy.actors.get()
    assert execution not in manager.proxy.activities.get()

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    state = Xml.load(config, 'simple').get_state()
    state['items']['start-node']['state'] = 'valid'

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
    })

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
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

    # the thing to test
    handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'user_identifier': manager.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'mid-form',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'data': {
                        '_type': 'field',
                        'state': 'valid',
                        'value': 'yes',
                    },
                },
                'item_order': ['data'],
            },
        }],
    }, channel)

    # assertions
    assert Pointer.get(p_0.id) is None

    assert Pointer.count() == 1
    assert Pointer.get_all()[0].node_id == 'final-node'

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

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
                'forms': [{
                    '_type': 'form',
                    'ref': 'mid-form',
                    'state': 'valid',
                    'inputs': {
                        '_type': ':sorted_map',
                        'items': {
                            'data': {
                                '_type': 'field',
                                'state': 'valid',
                                'value': 'yes',
                            },
                        },
                        'item_order': ['data'],
                    },
                }],
            },
        },
    }

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0

    # state
    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg['state'] == {
        '_type': ':sorted_map',
        'items': {
            'start-node': {
                '_type': 'node',
                'id': 'start-node',
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {},
                },
            },

            'mid-node': {
                '_type': 'node',
                'id': 'mid-node',
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
                            'forms': [{
                                '_type': 'form',
                                'ref': 'mid-form',
                                'state': 'valid',
                                'inputs': {
                                    '_type': ':sorted_map',
                                    'items': {
                                        'data': {
                                            '_type': 'field',
                                            'state': 'valid',
                                            'value': 'yes',
                                        },
                                    },
                                    'item_order': ['data'],
                                },
                            }],
                        },
                    },
                },
            },

            'final-node': {
                '_type': 'node',
                'id': 'final-node',
                'state': 'unfilled',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {},
                },
            },
        },
        'item_order': [
            'start-node',
            'mid-node',
            'final-node',
        ],
    }

    assert manager in execution.proxy.actors.get()
    assert execution in manager.proxy.activities.get()


def test_finish_execution(config, mongo):
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'manager')
    execution = p_0.proxy.execution.get()
    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'status': 'ongoing',
        'id': execution.id
    })

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())
    assert execution.id == reg['id']

    handler.finish_execution(execution)

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

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

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
            'started_at': datetime(2018, 4, 1, 21, 45),
            'finished_at': None,
            'status': 'ongoing',
            'id': execution_id
        })

    handler(channel, method, properties, body)

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

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
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    channel = MagicMock()

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': ptr.proxy.execution.get().id,
        },
        'node': {
            'id': 'approval-node',
        },
        'actors': {
            '_type': ':map',
            'items': {},
        },
    })

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'validation').get_state(),
    })

    # thing to test
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'accept',
                    },
                    'comment': {
                        'value': 'I like it',
                    },
                    'inputs': {
                        'value': [{
                            'ref': 'start-node.juan.0.task',
                        }],
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'final-node'

    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert_near_date(reg['finished_at'])
    assert reg['execution']['id'] == ptr.execution
    assert reg['node']['id'] == 'approval-node'
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
                'forms': [{
                    '_type': 'form',
                    'ref': 'approval',
                    'inputs': {
                        '_type': ':sorted_map',
                        'items': {
                            'response': {
                                'value': 'accept',
                            },
                            'comment': {
                                'value': 'I like it',
                            },
                            'inputs': {
                                'value': [{
                                    'ref': 'start-node.juan.0.task',
                                }],
                            },
                        },
                        'item_order': ['response', 'comment', 'inputs'],
                    },
                }],
            },
        },
    }


def test_reject(config, mongo):
    ''' tests that a rejection moves the pointer to a backward position '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': 'approval-node',
        },
        'actors': {
            '_type': ':map',
            'items': {},
        },
    })

    state = Xml.load(config, 'validation').get_state()

    state['items']['start-node']['state'] = 'valid'
    state['items']['start-node']['actors']['items']['juan'] = {
        '_type': 'actor',
        'state': 'valid',
        'user': {
            '_type': 'user',
            'identifier': 'juan',
            'fullname': 'Juan',
        },
        'forms': [{
            '_type': 'form',
            'ref': 'work',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        '_type': 'field',
                        'state': 'valid',
                        'value': '2',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
    })

    # thing to test
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'reject',
                    },
                    'comment': {
                        'value': 'I do not like it',
                    },
                    'inputs': {
                        'value': [{
                            'ref': 'start-node.juan.0:work.task',
                        }],
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'start-node'

    assert new_ptr in user.proxy.tasks

    # data is invalidated
    state = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    del state['_id']

    assert state == {
        '_type': 'execution',
        'id': execution.id,
        'state': {
            '_type': ':sorted_map',
            'items': {
                'start-node': {
                    '_type': 'node',
                    'id': 'start-node',
                    'state': 'invalid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'state': 'invalid',
                                    'ref': 'work',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'task': {
                                                '_type': 'field',
                                                'state': 'invalid',
                                                'value': '2',
                                            },
                                        },
                                        'item_order': ['task'],
                                    },
                                }],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },
                'approval-node': {
                    '_type': 'node',
                    'id': 'approval-node',
                    'state': 'invalid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'approval',
                                    'state': 'invalid',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'response': {
                                                'state': 'invalid',
                                                'value': 'reject',
                                            },
                                            'comment': {
                                                'value': 'I do not like it',
                                            },
                                            'inputs': {
                                                'value': [{
                                                    'ref': 'start-node.'
                                                           'juan.0:work.task',
                                                }],
                                            },
                                        },
                                        'item_order': [
                                            'response',
                                            'comment',
                                            'inputs',
                                        ],
                                    },
                                }],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },
                'final-node': {
                    '_type': 'node',
                    'id': 'final-node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                },
            },
            'item_order': ['start-node', 'approval-node', 'final-node'],
        },
    }

    # mongo has the data
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == ptr.execution
    assert reg['node']['id'] == 'approval-node'
    assert reg['actors'] == {
        '_type': ':map',
        'items': {
            'juan': {
                '_type': 'actor',
                'forms': [{
                    '_type': 'form',
                    'ref': 'approval',
                    'inputs': {
                        '_type': ':sorted_map',
                        'items': {
                            'response': {
                                'value': 'reject',
                            },
                            'comment': {
                                'value': 'I do not like it',
                            },
                            'inputs': {
                                'value': [{
                                    'ref': 'start-node.juan.0:work.task',
                                }],
                            },
                        },
                        'item_order': [
                            'response',
                            'comment',
                            'inputs',
                        ],
                    },
                }],
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

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'validation-reloaded').get_state(),
    })

    # first call to node1
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form1',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '1',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # first call to node2
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form2',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '1',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node3'

    # first call to node3
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form3',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '1',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # first call to validation
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'reject',
                    },
                    'comment': {
                        'value': 'I do not like it',
                    },
                    'inputs': {
                        'value': [{
                            'ref': 'node1.juan.0:form1.task',
                        }],
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node1'

    # second call to node1
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form1',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '2',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node2'

    # second call to node2
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form2',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '2',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node4'

    # second call to validation
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'accept',
                    },
                    'comment': {
                        'value': 'I like it',
                    },
                    'inputs': {
                        'value': None,
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node5'

    # first call to last node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            '_type': 'form',
            'ref': 'form5',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        'value': '1',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }, channel)
    assert Pointer.get_all() == []

    # state is coherent
    state = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find({
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
                    'id': 'node1',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'form1',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'task': {'value': '2'},
                                        },
                                        'item_order': ['task'],
                                    },
                                }],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },

                'node2': {
                    '_type': 'node',
                    'id': 'node2',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'form2',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'task': {'value': '2'},
                                        },
                                        'item_order': ['task'],
                                    },
                                }],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },

                'node3': {
                    '_type': 'node',
                    'id': 'node3',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'form3',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'task': {'value': '1'},
                                        },
                                        'item_order': ['task'],
                                    },
                                }],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },

                'node4': {
                    '_type': 'node',
                    'id': 'node4',
                    'state': 'valid',
                    'comment': 'I do not like it',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'approval',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'response': {
                                                'value': 'accept',
                                            },
                                            'comment': {
                                                'value': 'I like it',
                                            },
                                            'inputs': {
                                                'value': None,
                                            },
                                        },
                                        'item_order': [
                                            'response',
                                            'comment',
                                            'inputs',
                                        ],
                                    },
                                }],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },

                'node5': {
                    '_type': 'node',
                    'id': 'node5',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [{
                                    '_type': 'form',
                                    'ref': 'form5',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'items': {
                                            'task': {'value': '1'},
                                        },
                                        'item_order': ['task'],
                                    },
                                }],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                },
            },
            'item_order': ['node1', 'node2', 'node3', 'node4', 'node5'],
        },
        'status': 'finished',
    }


@pytest.mark.skip
def test_patch():
    ''' ensure that a patch request moves the pointer accordingly '''
    assert False


def test_resistance_unexisteng_hierarchy_backend(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
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

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
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

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
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

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
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
    ptr = make_pointer('condition.2018-05-17.xml', 'start-node')
    channel = MagicMock()

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'condition').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            {
                'ref': 'mistery',
                '_type': 'form',
                'inputs': {
                    '_type': ':sorted_map',
                    'item_order': [
                        'password',
                    ],
                    'items': {
                        'password': {
                            'type': 'text',
                            'value': 'abrete sésamo',
                        },
                    },
                },
            },
        ],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'mistical-node'


def test_elseif_condition_node(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start-node')
    channel = MagicMock()

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'condition').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            {
                'ref': 'mistery',
                '_type': 'form',
                'inputs': {
                    '_type': ':sorted_map',
                    'item_order': [
                        'password',
                    ],
                    'items': {
                        'password': {
                            'type': 'text',
                            'value': '123456',
                        },
                    },
                },
            },
        ],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == '123456-node'


def test_false_condition_node(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start-node')
    channel = MagicMock()

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'condition').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            {
                'ref': 'mistery',
                '_type': 'form',
                'inputs': {
                    '_type': ':sorted_map',
                    'item_order': [
                        'password',
                    ],
                    'items': {
                        'password': {
                            'type': 'text',
                            'value': 'npi',
                        },
                    },
                },
            },
        ],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'final-node'


def test_anidated_conditions(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('anidated-conditions.2018-05-17.xml', 'a')
    channel = MagicMock()

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'anidated-conditions').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            'ref': 'a',
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': ['a'],
                'items': {
                    'a': {'value': '1'},
                },
            },
        }],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'b'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            'ref': 'b',
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': ['b'],
                'items': {
                    'b': {'value': '0.00004'},
                },
            },
        }],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'c'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            'ref': 'c',
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': ['c'],
                'items': {
                    'c': {'value': '-1'},
                },
            },
        }],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'e'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            'ref': 'e',
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': ['e'],
                'items': {
                    'e': {'value': '-1'},
                },
            },
        }],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'f'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [{
            'ref': 'f',
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': ['f'],
                'items': {
                    'f': {'value': '-1'},
                },
            },
        }],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'g'
