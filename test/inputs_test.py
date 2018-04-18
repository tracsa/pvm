from datetime import datetime
from flask import json

from .utils import make_auth, make_activity, make_pointer, make_user


def test_all_inputs(client, models, config, mongo):
    user = make_user('juan', 'Juan')

    objeto = [
        {
            'ref': 'auth-form',
            'data': {
                'name': 'Algo',
                'datetime': datetime.now().isoformat()+'Z',
                'secret': '123456',
                'interests': ['science', 'music'],
                'gender': 'male',
                'elections': 'amlo',
            },
        },
    ]

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'all-inputs',
        'form_array': objeto
    }))

    assert res.status_code == 201
    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())
    actor = reg['actors'][0]

    assert actor['ref'] == 'inputs-node'
    assert actor['user']['identifier'] == 'juan'
    assert actor['forms'][0]['data'] == objeto[0]['data']


def test_datetime_error(client, models, mocker, config, mongo):
    objeto = [
        {
            'ref': 'auth-form',
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

    # assert res.status_code == 400


def test_visible_document_provider(client, models, mocker, config, mongo):
    res = client.get('/v1/process')

    body = json.loads(res.data)
    document_process = list(
        filter(
            lambda xml: xml['id'] == 'document', body['data']
        )
    )[0]

    assert res.status_code == 200
    assert document_process['form_array'][0] == {
        'ref': 'doc-form',
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


def test_allow_document(client, models, mocker, config, mongo):
    form_array = [
        {
            'ref': 'doc-form',
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


def test_deny_invalid_document(client, models, mocker, config, mongo):
    form_array = [
        {
            'ref': 'doc-form',
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
            'ref': 'doc-form',
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


def test_check_errors(client, models, mocker, config, mongo):
    objeto = [
        {
            'ref': 'auth-form',
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
            'ref': 'auth-form',
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


def test_radio_errors(client, models, mocker, config, mongo):
    objeto = [
        {
            'ref': 'auth-form',
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
            'ref': 'auth-form',
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


def test_select_errors(client, models, mocker, config, mongo):
    objeto = [
        {
            'ref': 'auth-form',
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
            'ref': 'auth-form',
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


def test_validate_form_multiple(client, models):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'single-form',
                'data': {
                    'name': 'jorge',
                },
            },
            {
                'ref': 'multiple-form',
                'data': {},
            },
        ],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': '\'phone\' input is required',
                'where': 'request.body.form_array.1.phone',
                'code': 'validation.required',
            },
        ]
    }


def test_validate_form_multiple_error_position(client, models):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'form-multiple',
        'form_array': [
            {
                'ref': 'single-form',
                'data': {
                    'name': 'jorge',
                },
            },
            {
                'ref': 'multiple-form',
                'data': {
                    'name': '12432',
                },
            },
            {
                'ref': 'multiple-form',
                'data': {},
            },
        ],
    }))

    # assert res.status_code == 400
    # assert json.loads(res.data) == {
    #     'errors': [
    #         {
    #             'detail': '\'phone\' input is required',
    #             'where': 'request.body.form_array.2.phone',
    #             'code': 'validation.required',
    #         },
    #     ]
    # }
