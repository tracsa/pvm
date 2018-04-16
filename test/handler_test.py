from datetime import datetime
from unittest.mock import MagicMock
from xml.dom.minidom import Document
import pika
import pytest
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.node import Node, make_node
from cacahuate.models import Execution, Pointer, User, Activity, Questionaire

from .utils import make_pointer, make_activity, make_user


def test_parse_message(config):
    handler = Handler(config)

    with pytest.raises(ValueError):
        handler.parse_message('not json')

    with pytest.raises(KeyError):
        handler.parse_message('{"foo":1}')

    with pytest.raises(ValueError):
        handler.parse_message('{"command":"foo"}')

    msg = handler.parse_message('{"command":"step"}')

    assert msg == {
        'command': 'step',
    }


def test_recover_step(config, models):
    handler = Handler(config)
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    exc = ptr.proxy.execution.get()

    execution, pointer, xmliter, node, *rest = \
        handler.recover_step({
            'command': 'step',
            'pointer_id': ptr.id,
            'actors': [
                {
                    'ref': 'requester',
                    'user': {'identifier': 'juan_manager'},
                    'forms': [
                        {
                            'ref': 'auth-form',
                            'data': {
                                'auth': 'yes',
                            },
                        },
                    ],
                }
            ],
        })

    assert execution.id == exc.id
    assert pointer.id == pointer.id
    assert pointer in execution.proxy.pointers

    conn = next(xmliter)
    assert conn.tagName == 'connector'
    assert conn.getAttribute('from') == 'mid-node'
    assert conn.getAttribute('to') == 'end-node'

    assert node.element.getAttribute('id') == 'mid-node'


def test_create_pointer(config, models):
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

    node = make_node(ele)
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


def test_wakeup(config, models, mongo):
    ''' the first stage in a node's lifecycle '''
    # setup stuff
    handler = Handler(config)

    pointer = make_pointer('exit_request.2018-03-20.xml', 'requester')
    execution = pointer.proxy.execution.get()
    juan = User(identifier='juan').save()
    manager = User(identifier='juan_manager').save()
    act = make_activity('requester', juan, execution)
    ques = Questionaire(ref='exit-form', data={'reason': 'why not'}).save()
    ques.proxy.execution.set(execution)

    channel = MagicMock()

    # this is what we test
    handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, channel)

    # test manager is notified
    channel.basic_publish.assert_called_once()
    channel.exchange_declare.assert_called_once()

    args = channel.basic_publish.call_args[1]

    assert args['exchange'] == config['RABBIT_NOTIFY_EXCHANGE']
    assert args['routing_key'] == 'email'
    assert json.loads(args['body']) == {
        'email': 'hardcoded@mailinator.com',
        'pointer': Pointer.get_all()[0].to_json(embed=['execution']),
    }

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    del reg['_id']

    assert (reg['started_at'] - datetime.now()).total_seconds() < 2
    assert reg['finished_at'] is None
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == 'manager'
    assert reg['actors'] == []
    assert reg['notified_users'] == [manager.to_json()]
    assert reg['state'] == {
        'forms': [{
            'ref': 'exit-form',
            'data': {
                'reason': 'why not',
            },
        }],
        'actors': [{
            'ref': 'requester',
            'user_id': juan.id,
        }],
    }

    # tasks where asigned
    assert manager.proxy.tasks.count() == 1

    task = manager.proxy.tasks.get()[0]

    assert isinstance(task, Pointer)
    assert task.node_id == 'manager'
    assert task.proxy.execution.get().id == execution.id


def test_teardown(config, models, mongo):
    ''' second and last stage of a node's lifecycle '''
    handler = Handler(config)

    p_0 = make_pointer('exit_request.2018-03-20.xml', 'manager')
    execution = p_0.proxy.execution.get()

    juan = User(identifier='juan').save()
    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    act = make_activity('manager', manager, execution)

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    form = Questionaire(ref='auth-form', data={
        'auth': 'yes',
    }).save()
    form.proxy.execution.set(execution)

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': p_0.node_id,
        },
        'actors': [],
        'state': {
            'forms': [
                {
                    'ref': 'exit-form',
                    'data': {
                        'reason': 'quiero salir',
                    },
                },
            ],
            'actors': [
                {
                    'ref': 'requester',
                    'user_id': juan.id,
                },
            ],
        },
    })

    channel = MagicMock()

    handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'actor': {
            'ref': 'a',
            'forms': [{
                'ref': form.ref,
                'data': form.data,
            }],
        },
    }, channel)

    assert Pointer.get(p_0.id) is None

    assert Pointer.count() == 1
    assert Pointer.get_all()[0].node_id == 'security'

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    del reg['_id']

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == p_0.node_id
    assert reg['actors'] == [{
        'ref': 'a',
        'forms': [{
            'ref': 'auth-form',
            'data': {
                'auth': 'yes',
            },
        }],
    }]
    assert reg['state'] == {
        'forms': [
            {
                'ref': 'exit-form',
                'data': {
                    'reason': 'quiero salir',
                },
            },
        ],
        'actors': [
            {
                'ref': 'requester',
                'user_id': juan.id,
            },
        ],
    }

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0


def test_teardown_start_process(config, models, mongo):
    ''' second and last stage of a node's lifecycle '''
    handler = Handler(config)

    p_0 = make_pointer('exit_request.2018-03-20.xml', 'manager')
    execution = p_0.proxy.execution.get()

    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    form = Questionaire(ref='auth-form', data={
        'auth': 'yes',
    }).save()
    form.proxy.execution.set(execution)

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': p_0.node_id,
        },
        'actors': [{
            'ref': 'a',
            'forms': [],
        }],
    })

    channel = MagicMock()

    handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
    }, channel)

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    del reg['_id']

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == p_0.node_id
    assert reg['actors'] == [{
        'ref': 'a',
        'forms': [],
    }]


def test_finish_execution(config, models, mongo):
    handler = Handler(config)

    p_0 = make_pointer('exit_request.2018-03-20.xml', 'manager')
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
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2


def test_call_trigger_recover(config, mongo, models):
    handler = Handler(config)
    channel = MagicMock()
    pointer = make_pointer('cyclic.2018-04-11.xml', 'jump-node')
    execution = pointer.proxy.execution.get()
    old_user = make_user('old', 'Old')
    p_user = make_user('present', 'Present')

    pques = Questionaire(ref='present', data={'a': '0'}).save()
    pques.proxy.execution.set(execution)

    act = make_activity('present', p_user, execution)

    def make_history(num):
        return {
            'node': {
                'id': 'start-node',
            },
            'execution': {
                'id': execution.id,
            },
            'started_at': datetime(2018, 4, num),
            'state': {
                'forms': [{
                    'ref': 'old',
                    'data': {
                        'a': str(num),
                    },
                }],
                'actors': [{
                    'ref': 'start-node',
                    'user_id': old_user.id,
                }],
            },
        }

    # insert some noisy registers in mongo for this node
    mongo[config['MONGO_HISTORY_COLLECTION']].insert_many([
        make_history(1),
        make_history(3),
        make_history(2),
    ])

    mongo[config['MONGO_EXECUTION_COLLECTION']].insert_one({
        'id': execution.id,
        'status': 'ongoing',
        'state': {
            'forms': [{
                'a': '0',
            }],
            'actors': [{
                'ref': 'present',
                'user': old_user.to_json(),
            }],
        },
    })

    # this is what we test
    handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, channel)

    # present questionary is deleted
    with pytest.raises(StopIteration):
        next(Questionaire.q().filter(ref='present'))

    # present actor is deleted
    with pytest.raises(StopIteration):
        next(Activity.q().filter(ref='present'))

    # Questionaries are restored
    ques = next(Questionaire.q().filter(ref='old'))

    assert ques in execution.proxy.forms
    assert ques.data == {
        'a': '3',
    }, 'last version of data is recovered'

    # actors are restored
    act = next(Activity.q().filter(ref='start-node'))

    assert act in execution.proxy.actors
    assert act.proxy.user.get() == old_user

    # execution collection has new state
    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg['status'] == 'ongoing'
    assert reg['id'] == execution.id
    assert reg['state'] == {
        'forms': [{
            'ref': 'old',
            'data': {
                'a': '3',
            },
        }],
        'actors': [{
            'ref': 'start-node',
            'user_id': old_user.id,
        }],
    }


def test_call_handler_delete_process(config, mongo, models):
    handler = Handler(config)
    channel = MagicMock()
    method = {'delivery_tag': True}
    properties = ""
    pointer = make_pointer('exit_request.2018-03-20.xml', 'requester')
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
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2

    assert Execution.count() == 0
    assert Pointer.count() == 0
    assert Questionaire.count() == 0
    assert Activity.count() == 0


def test_resistance_unexisteng_hierarchy_backend(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'noprov'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_hierarchy_return(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'return'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_hierarchy_item(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'item'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_node_not_found(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'nonode'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_dead_pointer(config):
    handler = Handler(config)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': 'nones',
    }))


def test_resistance_dead_execution(config):
    handler = Handler(config)

    ptr = Pointer().save()

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))
