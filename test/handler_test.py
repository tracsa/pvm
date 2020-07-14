from datetime import datetime
from unittest.mock import MagicMock
import simplejson as json

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
        name_template='nombre',
        description='description',
        description_template='description',
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
        'state': Xml.load(config, execution.process_name).get_state(),
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

    state = Xml.load(config, execution.process_name).get_state()
    state['items']['start_node']['state'] = 'valid'

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
                'value_caption': 'yes',
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
                        'value_caption': 'yes',
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
                                    'value_caption': 'yes',
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
        '_execution': [{
            'name': '',
            'description': '',
        }],
        'mid_form': [{
            'data': 'yes',
        }],
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

    ptr_id_1 = 'RANDOMPOINTERNAME'
    ptr_id_2 = 'MORERANDOMNAME'
    ptr_id_3 = 'NOTSORANDOMNAME'

    mongo[config["POINTER_COLLECTION"]].insert_many([
        {
            'execution': {
                'id': execution_id,
            },
            'state': 'finished',
            'id': ptr_id_1,
        },
        {
            'execution': {
                'id': execution_id,
            },
            'state': 'ongoing',
            'id': ptr_id_2,
        },
        {
            'execution': {
                'id': execution_id[::-1],
            },
            'state': 'ongoing',
            'id': ptr_id_3,
        },
    ])

    handler(channel, method, properties, body)

    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg['id'] == execution_id
    assert reg['status'] == "cancelled"
    assert_near_date(reg['finished_at'])

    assert Execution.count() == 0
    assert Pointer.count() == 0

    assert mongo[config["POINTER_COLLECTION"]].find_one({
        'id': ptr_id_1,
    })['state'] == 'finished'
    assert mongo[config["POINTER_COLLECTION"]].find_one({
        'id': ptr_id_2,
    })['state'] == 'cancelled'
    assert mongo[config["POINTER_COLLECTION"]].find_one({
        'id': ptr_id_3,
    })['state'] == 'ongoing'


def test_resistance_unexisteng_hierarchy_backend(config, mongo):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start_node')
    exc = ptr.proxy.execution.get()
    user = make_user('juan', 'Juan')

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name).get_state(),
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
        'state': Xml.load(config, exc.process_name).get_state(),
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
        'state': Xml.load(config, exc.process_name).get_state(),
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
        'state': Xml.load(config, exc.process_name).get_state(),
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


def test_compact_values(config):
    handler = Handler(config)
    names = [random_string() for _ in '123']

    values = handler.compact_values([
        Form.state_json('form1', [
            {
                'name': 'name',
                'type': 'text',
                'value': names[0],
            },
        ]),
        Form.state_json('form1', [
            {
                'name': 'name',
                'type': 'text',
                'value': names[1],
            },
        ]),
        Form.state_json('form2', [
            {
                'name': 'name',
                'type': 'text',
                'value': names[2],
            },
        ]),
    ])

    assert values == {
        'values.form1': [
            {
                'name': name,
            } for name in names[:2]
        ],
        'values.form2': [
            {
                'name': names[2],
            },
        ],
    }
