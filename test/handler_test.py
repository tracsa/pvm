from datetime import datetime
from xml.dom.minidom import Document
import json
import pika
import pytest

from pvm.handler import Handler
from pvm.node import Node, StartNode, make_node
from pvm.models import Execution, Pointer, User, Activity, Questionaire

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
    exc = Execution.validate(
        process_name = 'simple.2018-02-19.xml',
    ).save()
    ptr = Pointer.validate(
        node_id = '4g9lOdPKmRUf',
    ).save()
    ptr.proxy.execution.set(exc)

    execution, pointer, xmliter, node, forms, actors, documents = handler.recover_step({
        'command': 'step',
        'pointer_id': ptr.id,
        'forms':[
            {
                'ref': '#auth-form',
                'data': {
                    'auth': 'yes',
                },
            },
        ],
        'actors':  [
            {
                'ref': '#requester',
                'user': {'identifier':'juan_manager'}
            }
        ],
        'documents': []
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
    ele.setAttribute('class', 'dummy')
    ele.setAttribute('id', 'chubaca')

    node = make_node(ele)
    exc = Execution.validate(
        process_name = 'simple.2018-02-19.xml',
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

    execution = Execution(
        process_name = 'exit_request.2018-03-20.xml',
    ).save()
    juan = User(identifier='juan').save()
    manager = User(identifier='juan_manager').save()
    # this is needed in order to resolve the manager
    act = Activity(ref='#requester').save()
    act.proxy.user.set(juan)
    act.proxy.execution.set(execution)
    pointer = Pointer(
        node_id = 'employee-node',
    ).save()
    pointer.proxy.execution.set(execution)

    class Channel:

        def basic_publish(self, **kwargs):
            self.kwargs = kwargs

    channel = Channel()

    # this is what we test
    ptrs = handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, channel)

    # test manager is notified
    assert hasattr(channel, 'kwargs'), 'Publish was not called'

    args = channel.kwargs

    assert args['exchange'] == config['RABBIT_NOTIFY_EXCHANGE']
    assert args['routing_key'] == 'email'
    assert json.loads(args['body']) == {}

    # mongo has a registry
    reg = next(mongo.find())

    del reg['_id']

    assert (reg['started_at'] - datetime.now()).total_seconds() < 2
    assert reg['finished_at'] == None
    assert reg['execution_id'] == execution.id
    assert reg['node_id'] == 'manager-node'
    assert reg['forms'] == []
    assert reg['docs'] == []
    assert reg['actors'] == []

    # tasks where asigned
    assert manager.proxy.tasks.count() == 1

    task = manager.proxy.tasks.get()[0]

    assert isinstance(task, Pointer)
    assert task.node_id == 'manager-node'
    assert task.proxy.execution.get().id == execution.id

def test_finish_node(config, models, mongo):
    ''' second and last stage of a node's lifecycle '''
    handler = Handler(config)
    execution = Execution(
        process_name = 'exit_request.2018-03-20.xml',
    ).save()
    p_0 = Pointer(
        node_id = 'manager-node',
    ).save()
    p_0.proxy.execution.set(execution)
    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()
    act = Activity(ref='#manager').save()
    act.proxy.user.set(manager)
    act.proxy.execution.set(execution)
    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])
    form = Questionaire(ref='#auth-form', data={
        'auth' : 'yes',
    }).save()
    form.proxy.execution.set(execution)

    mongo.insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution_id': execution.id,
        'node_id': p_0.node_id,
        'forms': [],
        'docs': [],
        'actors': [],
    })

    ptrs = handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'forms': [{
            'ref': form.ref,
            'data': form.data,
        }],
    }, None)

    assert Pointer.get(p_0.id) == None
    assert len(ptrs) == 1
    assert ptrs[0].node_id == 'security-node'

    # mongo has a registry
    reg = next(mongo.find())

    del reg['_id']

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution_id'] == execution.id
    assert reg['node_id'] == p_0.node_id
    assert reg['forms'] == [{
        'ref': '#auth-form',
        'data': {
            'auth': 'yes',
        },
    }]

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0
