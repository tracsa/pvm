from unittest.mock import MagicMock
import requests

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.node import Form
from cacahuate.xml import Xml
from cacahuate.mongo import get_values

from .utils import make_pointer, make_user, random_string


def test_get_values():
    execution = {
        'values': {
            'form1': [
                {
                    'input1': 'A',
                },
                {
                    'input1': 'B',
                },
            ],
        },
    }

    context = get_values(execution)

    assert context['form1']['input1'] == 'B'
    assert list(context['form1'].all())[0]['input1'] == 'A'


def test_send_request_multiple(config, mongo, mocker):
    ''' Tests that values are stored in such a way that they can be iterated
    in a jinja template. Specifically in this test they'll be used as part of
    a request node, thus also testing that all of the values can be used '''
    # test setup
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
    ptr = make_pointer('request-multiple.2019-11-14.xml', 'start_node')
    execution = ptr.proxy.execution.get()
    channel = MagicMock()
    names = [random_string() for _ in '123']

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
    })

    handler.step({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            Form.state_json('form1', [
                {
                    'name': 'name',
                    'type': 'text',
                    'value': names[0],
                    'value_caption': names[0],
                },
            ]),
            Form.state_json('form1', [
                {
                    'name': 'name',
                    'type': 'text',
                    'value': names[1],
                    'value_caption': names[1],
                },
            ]),
            Form.state_json('form1', [
                {
                    'name': 'name',
                    'type': 'text',
                    'value': names[2],
                    'value_caption': names[2],
                },
            ]),
        ],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'request_node'

    # request is made with correct data
    requests.request.assert_called_once()
    args, kwargs = requests.request.call_args

    assert args[0] == 'POST'
    assert args[1] == 'http://localhost/'

    assert kwargs['data'] == '{{"names": ["{}","{}","{}"]}}'.format(*names)
    assert kwargs['headers'] == {
        'content-type': 'application/json',
    }
