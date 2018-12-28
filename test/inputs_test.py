from datetime import datetime
from flask import json
import pika
import pytest

from cacahuate.models import Execution
from cacahuate.node import Form

from .utils import make_auth, make_user, assert_near_date


def test_all_inputs(client, config, mongo, mocker):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'name': 'Algo',
                    'datetime': "2018-06-06T18:15:43.539603Z",
                    'secret': '123456',
                    'gender': 'female',
                    'interests': ['science', 'music'],
                    'elections': 'amlo',
                    'int': 15,
                    'float': 3.14,
                    'link': {
                        'label': 'DuckDuckGo',
                        'href': 'https://duckduckgo.com/',
                    }
                },
            },
        ],
    }))

    assert res.status_code == 201

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    json_message = {
        'name': {
            "name": "name",
            "type": "text",
            "value": "Algo",
            'label': 'Nombre',
            'value_caption': 'Algo',
            'state': 'valid',
            'hidden': False,
        },

        'datetime': {
            "name": "datetime",
            "type": "datetime",
            "value": "2018-06-06T18:15:43.539603Z",
            'label': 'Fecha de nacimiento',
            'value_caption': 'Wed Jun  6 18:15:43 2018',
            'state': 'valid',
            'hidden': False,
        },

        'secret': {
            "name": "secret",
            "type": "password",
            "value": "123456",
            'label': 'Un secreto',
            'value_caption': '******',
            'state': 'valid',
            'hidden': False,
        },

        'gender': {
            "name": "gender",
            "type": "radio",
            "value": "female",
            'label': 'Género?',
            'value_caption': 'Femenino',
            'state': 'valid',
            'hidden': False,
        },

        'interests': {
            "name": "interests",
            "type": "checkbox",
            "value": ['science', 'music'],
            'label': 'Marque sus intereses',
            'value_caption': 'Ciencia, Música',
            'state': 'valid',
            'hidden': False,
        },

        'elections': {
            "name": "elections",
            "type": "select",
            "value": "amlo",
            'label': 'Emita su voto',
            'value_caption': 'Andrés Manuel López Obrador',
            'state': 'valid',
            'hidden': False,
        },

        'int': {
            "name": "int",
            "type": "int",
            "value": 15,
            'label': 'Un entero',
            'value_caption': '15',
            'state': 'valid',
            'hidden': False,
        },

        'float': {
            "name": "float",
            "type": "float",
            "value": 3.14,
            'label': 'Un flotante',
            'value_caption': '3.14',
            'state': 'valid',
            'hidden': False,
        },

        'link': {
            'type': 'link',
            'name': 'link',
            'label': 'Give me the link',
            'state': 'valid',
            'hidden': False,
            'value': {
                'label': 'DuckDuckGo',
                'href': 'https://duckduckgo.com/',
            },
            'value_caption': {
                'label': 'DuckDuckGo',
                'href': 'https://duckduckgo.com/',
            },
        },
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    body = json.loads(args['body'])
    assert body['input'][0]['inputs']['items'] == json_message


def test_datetime_error(client, mocker, config):
    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': 'FECHA ERRONEA',
                'secret': '123456',
                'interests': ['science', 'music'],
                'gender': 'male',
                'elections': 'amlo',
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',

        'form_array': objeto
    }))

    assert res.status_code == 400


def test_visible_document_provider(client, mocker, config):
    res = client.get('/v1/process')

    body = json.loads(res.data)
    document_process = list(
        filter(
            lambda xml: xml['id'] == 'document', body['data']
        )
    )[0]

    assert res.status_code == 200
    assert document_process['form_array'][0] == {
        'ref': 'doc_form',
        'inputs': [
            {
                'label': 'Documento de identidad oficial',
                'name': 'identity_card',
                'provider': 'doqer',
                'required': True,
                'type': 'file',
            },
        ],
    }


def test_allow_document(client, mocker, config):
    form_array = [
        {
            'ref': 'doc_form',
            'data': {
                'identity_card': {
                    'id': 102214720680704176,
                    'mime': 'image/gif',
                    'name': 'credencial de elector',
                    'type': 'doqer:file',
                },
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'document',
        'form_array': form_array,
    }))

    assert res.status_code == 201


def test_deny_invalid_document(client, mocker, config):
    form_array = [
        {
            'ref': 'doc_form',
            'data': {
                'identity_card': {
                    'this': 'is invalid'
                },
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'document',
        'form_array': form_array,
    }))

    assert res.status_code == 400

    form_array = [
        {
            'ref': 'doc_form',
            'data': {
                'identity_card': 'also invalid'
            },
        },
    ]

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'document',
        'form_array': form_array,
    }))

    assert res.status_code == 400


def test_check_errors(client, mocker, config):
    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': 12,
                'gender': 'male',
                'elections': 'amlo',
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400

    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': ["science", "wrong"],
                'gender': 'male',
                'elections': 'amlo',
            },
        },
    ]

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400


def test_radio_errors(client, mocker, config):
    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': ["science"],
                'gender': [],
                'elections': 'amlo',
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400

    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': ["science", "wrong"],
                'gender': 'error',
                'elections': 'amlo',
            },
        },
    ]

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400


def test_select_errors(client, mocker, config):
    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': ["science"],
                'gender': "male",
                'elections': [],
            },
        },
    ]
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400

    objeto = [
        {
            'ref': 'auth_form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                'secret': '123456',
                'interests': ["science", "wrong"],
                'gender': "male",
                'elections': "error",
            },
        },
    ]

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 400


def test_validate_form_multiple(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'single_form',
                'data': {
                    'name': 'jorge',
                },
            },
            {
                'ref': 'multiple_form',
                'data': {},
            },
        ],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': '\'phone\' is required',
                'where': 'request.body.form_array.1.phone',
                'code': 'validation.required',
            },
        ]
    }


def test_validate_form_multiple_error_position(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'single_form',
                'data': {
                    'name': 'jorge',
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '12432',
                },
            },
            {
                'ref': 'multiple_form',
                'data': {},
            },
        ],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'code': 'validation.required',
                'detail': '\'phone\' is required',
                'where': 'request.body.form_array.2.phone',
            },
        ]
    }


@pytest.mark.skip
def test_can_send_no_form(client):
    ''' assert that a form that passes valudation does not ask for information
    in terms of the form count '''
    assert False


@pytest.mark.skip
def test_default_inputs(client):
    ''' do not send any value. Values set must be defaults '''
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'all-default-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {}
            },
        ],
    }))

    ques = None

    assert res.status_code == 201

    # text
    assert ques['data']['name'] == 'Jon Snow'
    # datetime
    assert_near_date(datetime.strptime(
        ques['data']['datetime'],
        "%Y-%m-%dT%H:%M:%S.%fZ"
    ))
    # password
    assert ques['data']['secret'] == 'dasdasd'
    # checkbox
    assert False
    # radio
    assert False
    # select
    assert False
    # file
    assert False


@pytest.mark.skip
def test_required_inputs_with_defaults(client):
    ''' all inputs are required but all of them have defaults '''
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'not-default-required-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {}
            },
        ],
    }))

    ques = None

    assert res.status_code == 201

    # text
    assert ques['data']['name'] == 'Jon Snow'
    # datetime
    assert_near_date(datetime.strptime(
        ques['data']['datetime'],
        "%Y-%m-%dT%H:%M:%S.%fZ"
    ))
    # password
    assert ques['data']['secret'] == 'dasdasd'
    # checkbox
    assert False
    # radio
    assert False
    # select
    assert False
    # file
    assert False


def test_start_with_correct_form_order(client, mocker, mongo, config):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'single_form',
                'data': {
                    'name': 'og',
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
        ],
    }))

    assert res.status_code == 201


def test_start_with_incorrect_form_order(client, mocker, mongo, config):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
            {
                'ref': 'multiple_form',
                'data': {
                    'phone': '3312345678'
                },
            },
            {
                'ref': 'single_form',
                'data': {
                    'name': 'og',
                },
            },
        ],
    }))

    assert res.status_code == 400


def test_hidden_input(client, mocker, config, mongo):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'input-hidden',
        'form_array': [{
            'ref': 'start_form',
            'data': {
                'data': 'yes',
            },
        }],
    }))

    assert res.status_code == 201

    exc = Execution.get_all()[0]
    ptr = exc.proxy.pointers.get()[0]

    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.\
        BlockingChannel.basic_publish.call_args[1]

    json_message = {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': 'juan',
        'input': [Form.state_json('start_form', [
            {
                'label': 'data',
                'type': 'text',
                'value': 'yes',
                'value_caption': 'yes',
                'name': 'data',
                'state': 'valid',
                'hidden': True,
            },
        ])],
    }

    assert json.loads(args['body']) == json_message


def test_link_input_none(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'link-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'link': None,
                },
            },
        ],
    }))

    assert res.status_code == 201


def test_link_input_malformed(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'link-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'link': 'google.com',
                },
            },
        ],
    }))

    assert res.status_code == 400

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'link-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'link': {
                        'name': 'google',
                        'href': 'https://google.com/',
                    },
                },
            },
        ],
    }))

    assert res.status_code == 400

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'link-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'link': 145,
                },
            },
        ],
    }))

    assert res.status_code == 400


def test_link_input_ok(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'link-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'link': {
                        'label': 'google',
                        'href': 'https://google.com/',
                    },
                },
            },
        ],
    }))

    assert res.status_code == 201


def test_float_input_none(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'float-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'float': None,
                },
            },
        ],
    }))

    assert res.status_code == 201


def test_float_input_malformed(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'float-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'float': {
                        'a': 'dict',
                    },
                },
            },
        ],
    }))

    assert res.status_code == 400

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'float-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'float': ['an', 'array'],
                },
            },
        ],
    }))

    assert res.status_code == 400

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'float-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'float': 'this string',
                },
            },
        ],
    }))

    assert res.status_code == 400


def test_float_input_ok(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'float-input',
        'form_array': [
            {
                'ref': 'auth_form',
                'data': {
                    'float': 15.6,
                },
            },
        ],
    }))

    assert res.status_code == 201
