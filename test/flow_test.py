from unittest.mock import MagicMock

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.xml import Xml
from cacahuate.node import Form, make_node

from .utils import make_user


def test_variable_proc_name(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    channel = MagicMock()
    xml = Xml.load(config, 'variable_name.2020-01-17.xml')
    xmliter = iter(xml)
    node = make_node(next(xmliter), xmliter)
    input = [Form.state_json('form01', [
        {
            'name': 'data01',
            'type': 'text',
            'value': '1',
            'value_caption': '1',
        },
    ])]
    execution = xml.start(node, input, mongo, channel, user.identifier)
    ptr = execution.proxy.pointers.get()[0]

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': input,
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node02'

    execution.reload()
    assert execution.name == 'Variable name process in step 1'
    assert execution.description == 'Description is also variable: 1, , '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form02', [
            {
                'name': 'data02',
                'type': 'text',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node03'

    execution.reload()
    assert execution.name == 'Variable name process in step 2'
    assert execution.description == 'Description is also variable: 1, 2, '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form03', [
            {
                'name': 'data03',
                'type': 'text',
                'value': '3',
                'value_caption': '3',
            },
        ])],
    }, channel)

    # test stops here because execution gets deleted


def test_variable_proc_name_mix(config, mongo):
    ''' Test where the name is related to
    multiple forms in diferent nodes of the execution'''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    channel = MagicMock()
    xml = Xml.load(config, 'variable_name_mix.2020-01-28.xml')
    xmliter = iter(xml)
    node = make_node(next(xmliter), xmliter)
    input = [Form.state_json('form01', [
        {
            'name': 'data01',
            'type': 'text',
            'value': '1',
            'value_caption': '1',
        },
    ])]
    execution = xml.start(node, input, mongo, channel, user.identifier)
    ptr = execution.proxy.pointers.get()[0]

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': input,
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node02'

    execution.reload()
    assert execution.name == 'Variable name process in step 10'
    assert execution.description == 'Description is also variable: 1, , '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form02', [
            {
                'name': 'data02',
                'type': 'text',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node03'

    execution.reload()
    assert execution.name == 'Variable name process in step 210'
    assert execution.description == 'Description is also variable: 1, 2, '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form03', [
            {
                'name': 'data03',
                'type': 'text',
                'value': '3',
                'value_caption': '3',
            },
        ])],
    }, channel)

    # test stops here because execution gets deleted


def test_variable_proc_name_pointers(config, mongo):
    ''' Test pointer name's update'''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    channel = MagicMock()
    xml = Xml.load(config, 'variable_name_mix.2020-01-28.xml')
    xmliter = iter(xml)
    node = make_node(next(xmliter), xmliter)
    input = [Form.state_json('form01', [
        {
            'name': 'data01',
            'type': 'text',
            'value': '1',
            'value_caption': '1',
        },
    ])]
    execution = xml.start(node, input, mongo, channel, user.identifier)
    ptr = execution.proxy.pointers.get()[0]

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': input,
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node02'

    execution.reload()
    assert execution.name == 'Variable name process in step 10'
    assert execution.description == 'Description is also variable: 1, , '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form02', [
            {
                'name': 'data02',
                'type': 'text',
                'value': '2',
                'value_caption': '2',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node03'

    execution.reload()
    assert execution.name == 'Variable name process in step 210'
    assert execution.description == 'Description is also variable: 1, 2, '

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form03', [
            {
                'name': 'data03',
                'type': 'text',
                'value': '3',
                'value_caption': '3',
            },
        ])],
    }, channel)

    # now check pointers last state
    cursor = mongo[config["POINTER_COLLECTION"]].find({
        'execution.id': execution.id,
    })

    assert cursor.count() == 3

    expected_name = 'Variable name process in step 3210'
    expected_desc = 'Description is also variable: 1, 2, 3'

    for item in cursor:
        assert item['execution']['name'] == expected_name
        assert item['execution']['description'] == expected_desc
