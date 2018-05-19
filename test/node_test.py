from cacahuate.xml import Xml
from cacahuate.node import make_node
from unittest.mock import MagicMock, patch
import requests


def test_resolve_params(config):
    xml = Xml.load(config, 'exit_request')
    xmliter = iter(xml)
    next(xmliter)
    node = make_node(next(xmliter))

    state = {
        'state': {
            'items': {
                'requester': {
                    'actors': {
                        'items': {
                            'juan': {
                                'user': {
                                    'identifier': 'juan',
                                },
                                'forms': [
                                    {
                                        'ref': 'sdfdfgg',
                                        'inputs': {
                                            'items': {
                                                'reason': {
                                                    'value': 'sdfgfs',
                                                },
                                            },
                                        },
                                    },
                                    {
                                        'ref': 'exit-form',
                                        'inputs': {
                                            'items': {
                                                'reason': {
                                                    'value': 'nones',
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    },
                },
            },
        },
    }

    assert node.resolve_params(state) == {
        "identifier": 'juan',
        "relation": 'manager',
        "reason": 'nones',
    }


def test_request_node(config, mocker):
    class ResponseMock:
        status_code = 200
        text = 'request response'

    mock = MagicMock(return_value=ResponseMock())

    mocker.patch(
        'requests.request',
        new = mock
    )

    xml = Xml.load(config, 'request.2018-05-18')
    xmliter = iter(xml)

    action = next(xmliter)
    request = next(xmliter)
    node = make_node(request)

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
    assert response == {
        'status_code': 200,
        'response': 'request response',
    }
