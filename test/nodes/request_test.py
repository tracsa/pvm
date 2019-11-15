from unittest.mock import MagicMock
import simplejson as json
import requests
import pytest
from random import randint
from xml.dom.minidom import parseString

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.node import Form, Capture
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


@pytest.mark.skip
def test_store_failed_decoding(config, mocker, mongo):
    # TODO set it up like test_store_data_from_response but make the json
    # decoding fail and test that the machine stays in a reasonably safe state
    assert False


@pytest.mark.skip
def test_store_failed_path(config, mocker, mongo):
    # TODO set it up like test_store_data_from_response but make the path not
    # match anything and test that the machine stays in a reasonably safe state
    assert False


def test_capture():
    name = random_string()
    label = random_string()
    field_name = random_string()

    dom = parseString('''<capture id="capture1">
      <value path="name" name="{}" label="{}" type="text"></value>
    </capture>'''.format(field_name, label)).documentElement
    capture = Capture(dom)

    assert capture.capture({
        'name': name,
    }) == [{
        'id': 'capture1',
        'items': [{
            'label': label,
            'name': field_name,
            'type': 'text',
            'value': name,
            'value_caption': name,
        }],
    }]


def test_capture_parent_path():
    name = random_string()
    label = random_string()
    field_name = random_string()

    dom = parseString('''<capture id="capture1" path="props">
      <value path="name" name="{}" label="{}" type="text"></value>
    </capture>'''.format(field_name, label)).documentElement
    capture = Capture(dom)

    assert capture.capture({
        'props': {
            'name': name,
        },
    }) == [{
        'id': 'capture1',
        'items': [{
            'label': label,
            'name': field_name,
            'type': 'text',
            'value': name,
            'value_caption': name,
        }],
    }]


def test_capture_multiple():
    name1 = random_string()
    name2 = random_string()
    label = random_string()
    field_name = random_string()

    dom = parseString('''<capture id="capture1" path="items" multiple="multiple">
      <value path="name" name="{}" label="{}" type="text"></value>
    </capture>'''.format(field_name, label)).documentElement
    capture = Capture(dom)

    assert capture.capture({
        'items': [
            {
                'name': name1,
            },
            {
                'name': name2,
            },
        ],
    }) == [{
        'id': 'capture1',
        'items': [{
            'label': label,
            'name': field_name,
            'type': 'text',
            'value': name1,
            'value_caption': name1,
        }],
    }, {
        'id': 'capture1',
        'items': [{
            'label': label,
            'name': field_name,
            'type': 'text',
            'value': name2,
            'value_caption': name2,
        }],
    }]


def test_store_data_from_response(config, mocker, mongo):
    expected_name = random_string()
    expected_age_1 = randint(0, 100)
    expected_age_2 = randint(0, 100)

    request_response = {
        'params': {
            'name': expected_name,
        },
        'items': [
            [
                {
                    'age': expected_age_1,
                },
                {
                    'age': expected_age_2,
                },
            ],
        ],
    }
    request_response_s = json.dumps(request_response)

    class ResponseMock:
        status_code = 200
        text = request_response_s

        def json(self):
            return request_response

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new=mock
    )

    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('request-captures.2019-08-08.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()
    value = random_string()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'request-captures').get_state(),
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
                'value': request_response_s,
                'value_caption': request_response_s,
                'hidden': False,
                'label': 'Response',
            },
        ]),
        Form.state_json('capture1', [
            {
                'name': 'name',
                'state': 'valid',
                'type': 'text',
                'value': expected_name,
                'value_caption': expected_name,
                'hidden': False,
                'label': 'Nombre',
            },
        ]),
        Form.state_json('capture2', [
            {
                'name': 'age',
                'state': 'valid',
                'type': 'int',
                'value': expected_age_1,
                'value_caption': str(expected_age_1),
                'hidden': False,
                'label': 'Edad',
            },
        ]),
        Form.state_json('capture2', [
            {
                'name': 'age',
                'state': 'valid',
                'type': 'int',
                'value': expected_age_2,
                'value_caption': str(expected_age_2),
                'hidden': False,
                'label': 'Edad',
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
    assert state['values'] == {
        'capture1': [{
            'name': expected_name,
        }],
        'capture2': [
            {
                'age': expected_age_1,
            },
            {
                'age': expected_age_2,
            },
        ],
        'request': [{
            'data': value,
        }],
        'request_node': [{
            'raw_response': request_response_s,
            'status_code': 200,
        }],
    }
