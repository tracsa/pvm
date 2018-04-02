from xml.dom.minidom import Document
import json
import pika
import pytest

from pvm.handler import Handler
from pvm.node import Node, StartNode, make_node
from pvm.models import Execution, Pointer, User, Activity

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

    execution, pointer, xmliter, node = handler.recover_step({
        'command': 'step',
        'pointer_id': ptr.id,
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

def test_call_recover(config, models):
    handler = Handler(config)
    execution = Execution(
        process_name = 'simple.2018-02-19.xml',
    ).save()
    pointer = Pointer(
        node_id = '4g9lOdPKmRUf',
    ).save()
    pointer.proxy.execution.set(execution)

    ptrs = handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, None)

    assert Pointer.get(pointer.id) == None
    assert Execution.get(execution.id) == None
    assert ptrs == []

def test_wakeup_notifies_manager(config, models):
    ''' a node whose auth has a filter must notify the people matching the
    filter '''
    # setup stuff
    handler = Handler(config)

    execution = Execution(
        process_name = 'exit_request.2018-03-20.xml',
    ).save()
    pointer = Pointer(
        node_id = 'employee-node',
    ).save()
    pointer.proxy.execution.set(execution)
    juan = User(identifier='juan').save()
    manager = User(identifier='juan_manager').save()
    act = Activity(ref='#requester').save()
    act.proxy.user.set(juan)
    act.proxy.execution.set(execution)

    class Channel:

        def basic_publish(self, **kwargs):
            self.kwargs = kwargs

    channel = Channel()

    # this is what we test
    ptrs = handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    }, channel)

    # the actual tests

    args = channel.kwargs

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_NOTIFY_QUEUE']
    assert json.loads(args['body']) == {}

def test_wakeup_inserts_log(mongo):
    assert False

def test_finish_completes_log(mongo):
    assert False
