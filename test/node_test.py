from unittest.mock import MagicMock
import requests

from cacahuate.xml import Xml
from cacahuate.node import make_node, Form


def test_resolve_params(config):
    xml = Xml.load(config, 'exit_request')
    xmliter = iter(xml)
    next(xmliter)
    node = make_node(next(xmliter), xmliter)

    state = {
        'values': {
            'exit_form': [{
                'reason': 'nones',
            }],
        },
        'actors': {
            'requester': 'juan',
        },
    }

    assert node.resolve_params(state) == {
        "identifier": 'juan',
        "relation": 'manager',
        "reason": 'nones',
    }


def test_get_actors(config):
    xml = Xml.load(config, 'noparam')
    xmliter = iter(xml)
    next(xmliter)
    node = make_node(next(xmliter), xmliter)

    found_users = node.get_actors(config, {})

    assert len(found_users) == 1
    assert found_users[0].identifier == 'foo'


def test_request_node(config, mocker):
    class ResponseMock:
        status_code = 200
        text = 'request response'

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new=mock
    )

    xml = Xml.load(config, 'request.2018-05-18')
    xmliter = iter(xml)

    next(xmliter)
    request = next(xmliter)
    node = make_node(request, xmliter)

    response = node.make_request({
        'request': {
            'data': '123456',
        },
    })

    requests.request.assert_called_once()
    args = requests.request.call_args

    method, url = args[0]
    data = args[1]['data']
    headers = args[1]['headers']

    assert method == 'GET'
    assert url == 'http://localhost/mirror?data=123456'
    assert headers == {
        'content-type': 'application/json',
        'x-url-data': '123456',
    }
    assert data == '{"data":"123456"}'
    assert response == [{
        'id': 'request_node',
        'items': [
            {
                'name': 'status_code',
                'value': 200,
                'type': 'int',
                'label': 'Status Code',
                'value_caption': '200',
            },
            {
                'name': 'raw_response',
                'value': 'request response',
                'type': 'text',
                'label': 'Response',
                'value_caption': 'request response',
            }
        ],
    }]


def test_form_state_json():
    assert Form.state_json('ref', []) == {
        '_type': 'form',
        'ref': 'ref',
        'state': 'valid',
        'inputs': {
            '_type': ':sorted_map',
            'items': {},
            'item_order': [],
        },
    }
