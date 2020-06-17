from unittest.mock import MagicMock
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer
from cacahuate.node import Form
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user


def test_true_condition_node(config, mongo):
    ''' conditional node will be executed if its condition is true '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start_node')
    execution = ptr.proxy.execution.get()
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('mistery', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'abrete sésamo',
                'value_caption': 'abrete sésamo',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition1'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition1', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'mistical_node'


def test_false_condition_node(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('condition.2018-05-17.xml', 'start_node')
    execution = ptr.proxy.execution.get()
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('mistery', [
            {
                'name': 'password',
                'type': 'text',
                'value': '123456',
                'value_caption': '123456',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition1'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition1', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition2'


def test_anidated_conditions(config, mongo):
    ''' conditional node won't be executed if its condition is false '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('anidated-conditions.2018-05-17.xml', 'a')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'anidated-conditions').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('a', [
            {
                'name': 'a',
                'value': '1',
                'value_caption': '1',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'outer'

    # rabbit called
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('outer', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'b'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('b', [
            {
                'name': 'b',
                'value': '-1',
                'value_caption': '-1',
            },
        ])],
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'inner1'

    # rabbit called
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('inner1', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    handler.call(rabbit_call, channel)

    # assertions
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'f'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('f', [
            {
                'name': 'f',
                'value': '-1',
                'value_caption': '-1',
            },
        ])],
    }, channel)

    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'g'


def test_ifelifelse_if(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'incorrect!',
                'value_caption': 'incorrect!',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action01'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
                'value_caption': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_ifelifelse_elif(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'hocus pocus',
                'value_caption': 'hocus pocus',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action02'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
                'value_caption': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_ifelifelse_else(config, mongo):
    ''' else will be executed if preceding condition is false'''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('else.2018-07-10.xml', 'start_node')
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': ptr.proxy.execution.get().id,
        'state': Xml.load(config, 'else').get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('secret01', [
            {
                'name': 'password',
                'type': 'text',
                'value': 'cuca',
                'value_caption': 'cuca',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'condition01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('condition01', [
            {
                'name': 'condition',
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'else01'

    # rabbit called
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('else01', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    channel = MagicMock()
    handler.call(rabbit_call, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'action03'

    # rabbit called to notify the user
    channel.basic_publish.assert_called_once()
    args = channel.basic_publish.call_args[1]
    assert args['exchange'] == 'charpe_notify'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'answer',
                'value': 'answer',
                'value_caption': 'answer',
            },
        ])],
    }, channel)

    # execution finished
    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0


def test_invalidated_conditional(config, mongo):
    ''' a condiitonal depends on an invalidated field, if it changes during
    the second response it must take the second value '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    process_filename = 'condition_invalidated.2019-10-08.xml'
    ptr = make_pointer(process_filename, 'start_node')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(
            config, execution.process_name
        ).get_state(),
    })

    # initial rabbit call
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'value',
                'type': 'int',
                'value': 3,
                'value_caption': '3',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # arrives to if_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'if_node'

    # if_node's condition is True
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('if_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # if rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to if_validation
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'if_validation_node'

    # if's call to validation
    channel.reset_mock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('if_validation_node', [
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
                    'ref': 'start_node.juan.0:form1.value',
                }],
                'value_caption': '',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # returns to start_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'start_node'

    # second lap
    channel.reset_mock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'value',
                'type': 'int',
                'value': -3,
                'value_caption': '-3',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # arrives to if_node again
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'if_node'

    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('if_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # if second rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to elif_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif_node'

    # elif node's condition is true
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # elif rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to elif_validation
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif_validation_node'

    # elif's call to validation
    channel.reset_mock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('elif_validation_node', [
            {
                'name': 'response',
                'value': 'reject',
                'value_caption': 'reject',
            },
            {
                'name': 'comment',
                'value': 'Ugly... nope',
                'value_caption': 'Ugly... nope',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:form1.value',
                }],
                'value_caption': '',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # returns to start_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'start_node'

    # third lap
    channel.reset_mock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form1', [
            {
                'name': 'value',
                'type': 'int',
                'value': 0,
                'value_caption': '0',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # arrives to if_node again again
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'if_node'

    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('if_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # if third rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to elif_node again
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'elif_node'

    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('elif_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # elif second rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to else_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'else_node'

    # else node's condition is true
    args = channel.basic_publish.call_args[1]
    rabbit_call = {
        'command': 'step',
        'pointer_id': ptr.id,
        'input': [Form.state_json('else_node', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])],
        'user_identifier': '__system__',
    }
    assert json.loads(args['body']) == rabbit_call

    # else rabbit call
    channel.reset_mock()
    handler.call(rabbit_call, channel)
    channel.basic_publish.assert_called_once()

    # arrives to if_validation
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'else_validation_node'

    # else's call to validation
    channel.reset_mock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('else_validation_node', [
            {
                'name': 'response',
                'value': 'reject',
                'value_caption': 'reject',
            },
            {
                'name': 'comment',
                'value': 'What? No!',
                'value_caption': 'What? No!',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:form1.value',
                }],
                'value_caption': '',
            },
        ])],
    }, channel)
    channel.basic_publish.assert_called_once()

    # returns to start_node
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'start_node'

    # state is coherent
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
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json(
                                    'form1',
                                    [
                                        {
                                            'name': 'value',
                                            'type': 'int',
                                            'value': 0,
                                            'value_caption': '0',
                                            'state': 'invalid',
                                        },
                                    ],
                                    state='invalid',
                                )],
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
                    'name': 'Node 1',
                    'description': 'the value subject to inspection',
                },

                'if_node': {
                    '_type': 'node',
                    'type': 'if',
                    'id': 'if_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            '__system__': {
                                '_type': 'actor',
                                'forms': [Form.state_json(
                                    'if_node',
                                    [
                                        {
                                            'name': 'condition',
                                            'value': False,
                                            'value_caption': 'False',
                                            'type': 'bool',
                                            'state': 'invalid',
                                        },
                                    ],
                                    state='invalid',
                                )],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': '__system__',
                                    'fullname': 'System',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'IF if_node',
                    'description': 'IF if_node',
                },

                'if_validation_node': {
                    '_type': 'node',
                    'type': 'validation',
                    'id': 'if_validation_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [Form.state_json(
                                    'if_validation_node',
                                    [
                                        {
                                            'name': 'response',
                                            'value': 'reject',
                                            'value_caption': 'reject',
                                            'state': 'invalid',
                                        },
                                        {
                                            'name': 'comment',
                                            'value': 'I do not like it',
                                            'value_caption': (
                                                'I do not like it'
                                            ),
                                        },
                                        {
                                            'name': 'inputs',
                                            'value': [{
                                                'ref': (
                                                    'start_node.juan.0:form1'
                                                    '.value'
                                                ),
                                            }],
                                            'value_caption': '',
                                        },
                                    ],
                                    state='invalid',
                                )],
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'fullname': 'Juan',
                                    'identifier': 'juan'
                                },
                            }
                        }
                    },
                    'name': 'The validation',
                    'description': 'This node invalidates the original value',
                    'milestone': False,
                },

                'elif_node': {
                    '_type': 'node',
                    'type': 'elif',
                    'id': 'elif_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            '__system__': {
                                '_type': 'actor',
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'fullname': 'System',
                                    'identifier': '__system__'
                                },
                                'forms': [Form.state_json(
                                    'elif_node',
                                    [
                                        {
                                            'name': 'condition',
                                            'value': False,
                                            'value_caption': 'False',
                                            'type': 'bool',
                                            'state': 'invalid',
                                        },
                                    ],
                                    state='invalid',
                                )],
                            }
                        }
                    },
                    'name': 'ELIF elif_node',
                    'description': 'ELIF elif_node',
                    'milestone': False,
                },

                'elif_validation_node': {
                    '_type': 'node',
                    'type': 'validation',
                    'id': 'elif_validation_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'fullname': 'Juan',
                                    'identifier': 'juan'
                                },
                                'forms': [Form.state_json(
                                    'elif_validation_node',
                                    [
                                        {
                                            'name': 'response',
                                            'value': 'reject',
                                            'value_caption': 'reject',
                                            'state': 'invalid',
                                        },
                                        {
                                            'name': 'comment',
                                            'value': 'Ugly... nope',
                                            'value_caption': (
                                                'Ugly... nope'
                                            ),
                                        },
                                        {
                                            'name': 'inputs',
                                            'value': [{
                                                'ref': (
                                                    'start_node.juan.0:form1'
                                                    '.value'
                                                ),
                                            }],
                                            'value_caption': '',
                                        },
                                    ],
                                    state='invalid',
                                )],
                            }
                        }
                    },
                    'name': 'The validation',
                    'description': (
                        'This node also invalidates the original value'
                    ),
                    'milestone': False,
                },

                'else_node': {
                    '_type': 'node',
                    'type': 'else',
                    'id': 'else_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            '__system__': {
                                '_type': 'actor',
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'fullname': 'System',
                                    'identifier': '__system__'
                                },
                                'forms': [Form.state_json(
                                    'else_node',
                                    [
                                        {
                                            'name': 'condition',
                                            'value': True,
                                            'value_caption': 'True',
                                            'type': 'bool',
                                            'state': 'invalid',
                                        },
                                    ],
                                    state='invalid',
                                )],
                            }
                        }
                    },
                    'name': 'ELSE else_node',
                    'description': 'ELSE else_node',
                    'milestone': False,
                },

                'else_validation_node': {
                    '_type': 'node',
                    'type': 'validation',
                    'id': 'else_validation_node',
                    'state': 'invalid',
                    'comment': 'What? No!',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'state': 'invalid',
                                'user': {
                                    '_type': 'user',
                                    'fullname': 'Juan',
                                    'identifier': 'juan'
                                },
                                'forms': [Form.state_json(
                                    'else_validation_node',
                                    [
                                        {
                                            'name': 'response',
                                            'value': 'reject',
                                            'value_caption': 'reject',
                                            'state': 'invalid',
                                        },
                                        {
                                            'name': 'comment',
                                            'value': 'What? No!',
                                            'value_caption': 'What? No!',
                                        },
                                        {
                                            'name': 'inputs',
                                            'value': [{
                                                'ref': (
                                                    'start_node.juan.0:form1'
                                                    '.value'
                                                ),
                                            }],
                                            'value_caption': '',
                                        },
                                    ],
                                    state='invalid'),
                                ],
                            }
                        }
                    },
                    'name': 'The validation',
                    'description': (
                        'This node invalidates the original value, too'
                    ),
                    'milestone': False,
                }
            },
            'item_order': [
                'start_node',
                'if_node',
                'if_validation_node',
                'elif_node',
                'elif_validation_node',
                'else_node',
                'else_validation_node'
            ],
        },

        'values': {
            'form1': [
                {
                    'value': 0,
                }
            ],
            'if_node': [
                {
                    'condition': False,
                }
            ],
            'if_validation_node': [
                {
                    'response': 'reject',
                    'comment': 'I do not like it',
                    'inputs': [
                        {
                            'ref': 'start_node.juan.0:form1.value'
                        },
                    ],
                },
            ],
            'elif_node': [
                {
                    'condition': False,
                },
            ],
            'elif_validation_node': [
                {
                    'response': 'reject',
                    'comment': 'Ugly... nope',
                    'inputs': [
                        {
                            'ref': 'start_node.juan.0:form1.value',
                        },
                    ],
                },
            ],
            'else_node': [
                {
                    'condition': True,
                },
            ],
            'else_validation_node': [
                {
                    'response': 'reject',
                    'comment': 'What? No!',
                    'inputs': [
                        {
                            'ref': 'start_node.juan.0:form1.value',
                        },
                    ],
                },
            ],
        },

        'actors': {
            'start_node': 'juan',
            'if_node': '__system__',
            'if_validation_node': 'juan',
            'elif_node': '__system__',
            'elif_validation_node': 'juan',
            'else_node': '__system__',
            'else_validation_node': 'juan',
        },

        'actor_list': [
            {
                'node': 'start_node',
                'identifier': 'juan',
            },
            {
                'node': 'if_node',
                'identifier': '__system__',
            },
            {
                'node': 'if_validation_node',
                'identifier': 'juan',
            },
            {
                'node': 'elif_node',
                'identifier': '__system__',
            },
            {
                'node': 'elif_validation_node',
                'identifier': 'juan',
            },
            {
                'node': 'else_node',
                'identifier': '__system__',
            },
            {
                'node': 'else_validation_node',
                'identifier': 'juan',
            }
        ],
    }
