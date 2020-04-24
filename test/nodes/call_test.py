from unittest.mock import MagicMock
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer
from cacahuate.node import Form
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user, random_string


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
        'state': Xml.load(config, execution.process_name).get_state(),
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
                'value_caption': value,
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


def test_call_node(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('call-render.2020-04-24.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
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
                'value_caption': value,
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
