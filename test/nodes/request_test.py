from unittest.mock import MagicMock
import simplejson as json
import requests

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.node import Form
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user, random_string


def test_handle_request_node(config, mocker, mongo):
    class ResponseMock:
        status_code = 200
        text = 'request response'

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new=mock
    )

    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('request.2018-05-18.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'request').get_state(),
    })

    # teardown of first node and wakeup of request node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('request', [
            {
                'name': 'data',
                'value': value
            },
        ])],
    }, channel)
    assert Pointer.get(ptr.id) is None
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'request_node'

    # assert requests is called
    requests.request.assert_called_once()
    args, kwargs = requests.request.call_args

    assert args[0] == 'GET'
    assert args[1] == 'http://localhost/mirror?data=' + value

    assert kwargs['data'] == '{"data":"' + value + '"}'
    assert kwargs['headers'] == {
        'content-type': 'application/json',
        'x-url-data': value,
    }

    # aditional rabbit call for new process
    args = channel.basic_publish.call_args_list[0][1]

    expected_inputs = [Form.state_json('request_node', [
        {
            'name': 'status_code',
            'state': 'valid',
            'type': 'int',
            'value': 200,
            'value_caption': '200',
            'hidden': False,
            'label': 'Status Code',
        },
        {
            'name': 'raw_response',
            'state': 'valid',
            'type': 'text',
            'value': 'request response',
            'value_caption': 'request response',
            'hidden': False,
            'label': 'Response',
        },
    ])]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }, channel)

    state = mongo[config["EXECUTION_COLLECTION"]].find_one({
        'id': execution.id,
    })

    assert state['state']['items']['request_node'] == {
        '_type': 'node',
        'type': 'request',
        'id': 'request_node',
        'comment': '',
        'state': 'valid',
        'actors': {
            '_type': ':map',
            'items': {
                '__system__': {
                    '_type': 'actor',
                    'state': 'valid',
                    'user': {
                        '_type': 'user',
                        'fullname': 'System',
                        'identifier': '__system__',
                    },
                    'forms': expected_inputs,
                },
            },
        },
        'milestone': False,
        'name': 'Request request_node',
        'description': 'Request request_node',
    }


def test_store_data_from_response(config, mocker, mongo):
    class ResponseMock:
        status_code = 200
        text = 'request response'

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new=mock
    )

    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('request-storage.2019-08-08.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'request-storage').get_state(),
    })

    # teardown of first node and wakeup of request node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('request', [
            {
                'name': 'data',
                'value': value
            },
        ])],
    }, channel)
    assert Pointer.get(ptr.id) is None
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'request_node'

    # assert requests is called
    requests.request.assert_called_once()
    args, kwargs = requests.request.call_args

    assert args[0] == 'GET'
    assert args[1] == 'http://localhost/'

    assert kwargs['data'] == ''
    assert kwargs['headers'] == {
        'content-type': 'application/json',
    }

    # aditional rabbit call for new process
    args = channel.basic_publish.call_args_list[0][1]

    expected_inputs = [
        Form.state_json('request_node', [
            {
                'name': 'status_code',
                'state': 'valid',
                'type': 'int',
                'value': 200,
                'value_caption': '200',
                'hidden': False,
                'label': 'Status Code',
            },
            {
                'name': 'raw_response',
                'state': 'valid',
                'type': 'text',
                'value': 'request response',
                'value_caption': 'request response',
                'hidden': False,
                'label': 'Response',
            },
        ]),
        Form.state_json('capture1', [
            {
                'name': 'status_code',
                'state': 'valid',
                'type': 'int',
                'value': 200,
                'value_caption': '200',
                'hidden': False,
                'label': 'Status Code',
            },
        ]),
        Form.state_json('capture2', [
            {
                'name': 'status_code',
                'state': 'valid',
                'type': 'int',
                'value': 200,
                'value_caption': '200',
                'hidden': False,
                'label': 'Status Code',
            },
        ]),
        Form.state_json('capture2', [
            {
                'name': 'status_code',
                'state': 'valid',
                'type': 'int',
                'value': 200,
                'value_caption': '200',
                'hidden': False,
                'label': 'Status Code',
            },
        ]),
    ]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': expected_inputs,
    }, channel)

    state = mongo[config["EXECUTION_COLLECTION"]].find_one({
        'id': execution.id,
    })

    assert state['state']['items']['request_node'] == {
        '_type': 'node',
        'type': 'request',
        'id': 'request_node',
        'comment': '',
        'state': 'valid',
        'actors': {
            '_type': ':map',
            'items': {
                '__system__': {
                    '_type': 'actor',
                    'state': 'valid',
                    'user': {
                        '_type': 'user',
                        'fullname': 'System',
                        'identifier': '__system__',
                    },
                    'forms': expected_inputs,
                },
            },
        },
        'milestone': False,
        'name': 'Request request_node',
        'description': 'Request request_node',
    }
