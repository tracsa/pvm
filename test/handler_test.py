import xml.etree.ElementTree as ET
import pytest

from pvm.handler import Handler
from pvm.node import Node, StartNode, make_node
from pvm.models import Execution, Pointer

def test_parse_message(config):
    handler = Handler(config)

    with pytest.raises(ValueError):
        handler.parse_message('not json')

    with pytest.raises(KeyError):
        handler.parse_message('{"foo":1}')

    with pytest.raises(ValueError):
        handler.parse_message('{"command":"foo"}')

    msg = handler.parse_message('{"command":"start"}')

    assert msg == {
        'command': 'start',
    }

def test_get_start_node(config, models):
    handler = Handler(config)

    execution, pointer, xmliter, start_node = handler.get_start({
        'process': 'simple',
    })

    conn = next(xmliter)

    assert conn.tag == 'connector'

    assert start_node is not None
    assert isinstance(start_node, Node)
    assert isinstance(start_node, StartNode)

    assert execution.process_name == 'simple_2018-02-19.xml'
    assert execution.proxy.pointers.count() == 1
    assert pointer in execution.proxy.pointers

def test_recover_step(config, models):
    handler = Handler(config)
    exc = Execution.validate(
        process_name = 'simple_2018-02-19.xml',
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
    assert conn.tag == 'connector'
    assert conn.attrib == {'from':"4g9lOdPKmRUf", 'to':"kV9UWSeA89IZ"}

    assert node.id == '4g9lOdPKmRUf'

def test_create_pointer(config):
    handler = Handler(config)

    ele = ET.Element('node', {
        'class': 'dummy',
        'id': 'chubaca',
    })
    node = make_node(ele)
    exc = Execution.validate(
        process_name = 'simple_2018-02-19.xml',
    ).save()
    pointer = handler.create_pointer(node, exc)
    execution = pointer.proxy.execution.get()

    assert pointer.node_id == 'chubaca'

    assert execution.process_name == 'simple_2018-02-19.xml'
    assert execution.proxy.pointers.count() == 1

def test_call_start(config, models):
    handler = Handler(config)

    ptrs = handler.call({
        'command': 'start',
        'process': 'simple',
    })

    execution = Execution.get_all()[0]
    assert execution.process_name == 'simple_2018-02-19.xml'

    pointer = execution.proxy.pointers.get()[0]
    assert pointer.node_id == '4g9lOdPKmRUf'

    assert ptrs[0].id == pointer.id

def test_call_recover(config):
    handler = Handler(config)
    execution = Execution(
        process_name = 'simple_2018-02-19.xml',
    ).save()
    pointer = Pointer(
        node_id = '4g9lOdPKmRUf',
    ).save()
    pointer.proxy.execution.set(execution)

    ptrs = handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
    })

    assert Pointer.get(pointer.id) == None
    assert Execution.get(execution.id) == None
    assert ptrs == []
