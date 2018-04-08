from datetime import datetime
from xml.dom.minidom import Document
import simplejson as json
import pika
import pytest

from cacahuate.handler import Handler
from cacahuate.node import Node, make_node
from cacahuate.models import Execution, Pointer, User, Activity, Questionaire

from .utils import make_pointer, make_activity


class MockChannel:

    def __init__(self):
        self.bp_kwargs = None
        self.bp_call_count = 0
        self.ed_kwargs = None
        self.ed_call_count = 0

    def basic_publish(self, **kwargs):
        self.bp_kwargs = kwargs
        self.bp_call_count += 1

    def exchange_declare(self, **kwargs):
        self.ed_kwargs = kwargs
        self.ed_call_count += 1


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
    ptr = make_pointer('simple.2018-02-19.xml', '4g9lOdPKmRUf')
    exc = ptr.proxy.execution.get()

    execution, pointer, xmliter, node, *rest = \
        handler.recover_step({
            'command': 'step',
            'pointer_id': ptr.id,
            'actors': [
                {
                    'ref': '#requester',
                    'user': {'identifier': 'juan_manager'},
                    'forms': [
                        {
                            'ref': '#auth-form',
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
    assert conn.getAttribute('from') == '4g9lOdPKmRUf'
    assert conn.getAttribute('to') == 'kV9UWSeA89IZ'

    assert node.element.getAttribute('id') == '4g9lOdPKmRUf'


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
    act = make_activity('#requester', juan, execution)

    channel = MockChannel()

    # this is what we test
    ptrs = handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, channel)

    # test manager is notified
    assert channel.bp_call_count == 1
    assert channel.ed_call_count == 1

    args = channel.bp_kwargs

    assert args['exchange'] == config['RABBIT_NOTIFY_EXCHANGE']
    assert args['routing_key'] == 'email'
    assert json.loads(args['body']) == {
        'email': 'hardcoded@mailinator.com',
    }

    # mongo has a registry
    reg = next(mongo.find())

    del reg['_id']

    assert (reg['started_at'] - datetime.now()).total_seconds() < 2
    assert reg['finished_at'] is None
    assert reg['execution_id'] == execution.id
    assert reg['node_id'] == 'manager'
    assert reg['actors'] == []

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

    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    act = make_activity('#manager', manager, execution)

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    form = Questionaire(ref='#auth-form', data={
        'auth': 'yes',
    }).save()
    form.proxy.execution.set(execution)

    mongo.insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution_id': execution.id,
        'node_id': p_0.node_id,
        'actors': [],
    })

    channel = MockChannel()

    ptrs = handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'actor': {
            'ref': '#a',
            'forms': [{
                'ref': form.ref,
                'data': form.data,
            }],
        },
    }, channel)

    assert Pointer.get(p_0.id) is None
    assert len(ptrs) == 0

    assert Pointer.count() == 1
    assert Pointer.get_all()[0].node_id == 'security'

    # mongo has a registry
    reg = next(mongo.find())

    del reg['_id']

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution_id'] == execution.id
    assert reg['node_id'] == p_0.node_id
    assert reg['actors'] == [{
        'ref': '#a',
        'forms': [{
            'ref': '#auth-form',
            'data': {
                'auth': 'yes',
            },
        }],
    }]

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0
