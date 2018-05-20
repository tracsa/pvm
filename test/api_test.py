from cacahuate.handler import Handler
from cacahuate.models import Pointer, Execution
from datetime import datetime
from datetime import timedelta
from flask import json, jsonify, g
from random import choice
from string import ascii_letters
import pika
import pytest

from cacahuate.xml import Xml
from .utils import make_auth, make_pointer, make_user, \
    make_date, assert_near_date

EXECUTION_ID = '15asbs'


def test_continue_process_asks_for_user(client):
    res = client.post('/v1/pointer')

    assert res.status_code == 401
    assert 'WWW-Authenticate' in res.headers
    assert res.headers['WWW-Authenticate'] == \
        'Basic realm="User Visible Realm"'
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }],
    }


def test_continue_process_requires(client):
    user = make_user('juan', 'Juan')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({}))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'execution_id' is required",
                'code': 'validation.required',
                'where': 'request.body.execution_id',
            },
            {
                'detail': "'node_id' is required",
                'code': 'validation.required',
                'where': 'request.body.node_id',
            },
        ],
    }


def test_continue_process_asks_living_objects(client):
    ''' the app must validate that the ids sent are real objects '''
    user = make_user('juan', 'Juan')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': 'verde',
        'node_id': 'nada',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'execution_id is not valid',
                'code': 'validation.invalid',
                'where': 'request.body.execution_id',
            },
        ],
    }


def test_continue_process_requires_valid_node(client):
    user = make_user('juan', 'Juan')
    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'notarealnode',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'node_id is not a valid node',
                'code': 'validation.invalid_node',
                'where': 'request.body.node_id',
            },
        ],
    }


def test_continue_process_requires_living_pointer(client):
    user = make_user('juan', 'Juan')
    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'mid-node',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'node_id does not have a live pointer',
                'code': 'validation.no_live_pointer',
                'where': 'request.body.node_id',
            },
        ],
    }


def test_continue_process_requires_user_hierarchy(client):
    ''' a node whose auth has a filter must be completed by a person matching
    the filter '''
    user = make_user('juan', 'Juan')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': ptr.proxy.execution.get().id,
        'node_id': ptr.node_id,
    }))

    assert res.status_code == 403
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'Provided user does not have this task assigned',
            'where': 'request.authorization',
        }],
    }


def test_continue_process_requires_data(client):
    juan = make_user('juan', 'Juan')

    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    manager.proxy.tasks.set([ptr])

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(manager)}, data=json.dumps({
        'execution_id': ptr.proxy.execution.get().id,
        'node_id': ptr.node_id,
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [{
            'detail': "form count lower than expected for ref mid-form",
            'where': 'request.body.form_array',
        }],
    }


def test_continue_process(client, mocker, config):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    manager.proxy.tasks.set([ptr])
    exc = ptr.proxy.execution.get()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(manager)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': ptr.node_id,
        'form_array': [
            {
                'ref': 'mid-form',
                'data': {
                    'data': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 202
    assert json.loads(res.data) == {
        'data': 'accepted',
    }

    # rabbit is called
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    json_message = {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': 'juan_manager',
        'input': [{
            '_type': 'form',
            'ref': 'mid-form',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'data': {
                        "name": "data",
                        "type": "text",
                        "value": "yes",
                        'label': 'data',
                        'value_caption': 'yes',
                        'state': 'valid',
                    },
                },
                'item_order': ['data'],
            },
        }],
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    body = json.loads(args['body'])
    assert body == json_message

    # makes a useful call for the handler
    handler = Handler(config)

    pointer, user, inputs = handler.recover_step(json_message)

    assert pointer.id == ptr.id


def test_start_process_requirements(client, mongo, config):
    # first requirement is to have authentication
    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
        'process_name': 'simple',
    }))

    assert res.status_code == 401
    assert 'WWW-Authenticate' in res.headers
    assert res.headers['WWW-Authenticate'] == \
        'Basic realm="User Visible Realm"'
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }],
    }

    assert Execution.count() == 0

    # next, validate the form data
    user = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'simple',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [{
            'detail': "form count lower than expected for ref start_form",
            'where': 'request.body.form_array',
        }],
    }

    assert Execution.count() == 0
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data='{}')

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'process_name' is required",
                'where': 'request.body.process_name',
                'code': 'validation.required',
            },
        ],
    }

    # we need an existing process to start
    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'foo',
    }))

    assert res.status_code == 404
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'foo process does not exist',
                'where': 'request.body.process_name',
            },
        ],
    }

    # no registry should be created yet
    assert mongo[config["POINTER_COLLECTION"]].count() == 0


def test_start_process(client, mocker, config, mongo):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [{
            'ref': 'start_form',
            'data': {
                'data': 'yes',
            },
        }],
    }))

    assert res.status_code == 201

    exc = Execution.get_all()[0]

    assert exc.process_name == 'simple.2018-02-19.xml'

    ptr = exc.proxy.pointers.get()[0]

    assert ptr.node_id == 'start-node'

    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.\
        BlockingChannel.basic_publish.call_args[1]

    json_message = {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': 'juan',
        'input': [{
            '_type': 'form',
            'ref': 'start_form',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'data': {
                        'label': 'Info',
                        'type': 'text',
                        'value': 'yes',
                        'value_caption': 'yes',
                        'name': 'data',
                        'state': 'valid',
                    },
                },
                'item_order': ['data'],
            },
        }],
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == json_message

    handler = Handler(config)

    pointer, user, input = handler.recover_step(json_message)

    assert pointer.id == ptr.id

    # mongo has a registry
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert_near_date(reg['started_at'])
    assert reg['finished_at'] is None
    assert reg['execution']['id'] == exc.id
    assert reg['node']['id'] == ptr.node_id

    reg = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert_near_date(reg['started_at'])

    del reg['started_at']
    del reg['_id']

    assert reg == {
        '_type': 'execution',
        'id': exc.id,
        'name': exc.name,
        'description': exc.description,
        'status': 'ongoing',
        'finished_at': None,
        'status': 'ongoing',
        'state': {
            '_type': ':sorted_map',
            'items': {
                'start-node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'start-node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                },
                'mid-node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'mid-node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                },
                'final-node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'final-node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                },
            },
            'item_order': [
                'start-node',
                'mid-node',
                'final-node',
            ],
        },
        'values': {},
        'actors': {},
    }


def test_regression_requirements(client):
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    exc = ptr.proxy.execution.get()
    user.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'response' is required",
                'code': 'validation.required',
                'where': 'request.body.response',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': ''.join(choice(ascii_letters) for c in range(10)),
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'response' value invalid",
                'code': 'validation.invalid',
                'where': 'request.body.response',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'reject',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'inputs' is required",
                'code': 'validation.required',
                'where': 'request.body.inputs',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'reject',
        'inputs': 'de',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'inputs' must be a list",
                'code': 'validation.required_list',
                'where': 'request.body.inputs',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'reject',
        'inputs': ['de'],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'inputs.0' must be an object",
                'code': 'validation.required_dict',
                'where': 'request.body.inputs.0',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'reject',
        'inputs': [{
        }],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'inputs.0.ref' is required",
                'code': 'validation.required',
                'where': 'request.body.inputs.0.ref',
            },
        ],
    }

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'reject',
        'inputs': [{
            'ref': 'de',
        }],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': "'inputs.0.ref' value invalid",
                'code': 'validation.invalid',
                'where': 'request.body.inputs.0.ref',
            },
        ],
    }


def test_regression_approval(client, mocker, config):
    ''' the api for an approval '''
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    exc = ptr.proxy.execution.get()
    user.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval-node',
        'response': 'accept',
        'comment': 'I like the previous work',
    }))

    assert res.status_code == 202

    # rabbit is called
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.basic_publish \
        .call_args[1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': 'juan',
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'accept',
                    },
                    'comment': {
                        'value': 'I like the previous work',
                    },
                    'inputs': {
                        'value': None,
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }


def test_regression_reject(client, mocker, config):
    ''' the api for a reject '''
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    exc = ptr.proxy.execution.get()
    user.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': ptr.node_id,
        'response': 'reject',
        'comment': 'I dont like it',
        'inputs': [{
            'ref': 'start-node.juan.0:work.task',
        }],
    }))

    assert res.status_code == 202

    # rabbit is called
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.basic_publish \
        .call_args[1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': 'juan',
        'input': [{
            '_type': 'form',
            'ref': 'approval',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': 'reject',
                    },
                    'comment': {
                        'value': 'I dont like it',
                    },
                    'inputs': {
                        'value': [{
                            'ref': 'start-node.juan.0:work.task',
                        }],
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }],
    }


@pytest.mark.skip
def test_regression_patch_requirements():
    assert False, 'inputs are present'
    assert False, 'every field is valid'


@pytest.mark.skip
def test_regression_patch():
    ''' patch arbitrary data and cause a regression '''
    juan = make_user('juan', 'Juan')

    res = client.patch('/v1/execution/{}'.format(execution.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'a comment',
        'inputs': [{
            'ref': '',
        }],
    }))

    assert res.status_code == 202

    assert False, 'comment is saved'
    assert False, 'message is queued'


def test_list_processes(client):
    res = client.get('/v1/process')

    body = json.loads(res.data)
    exit_req = list(filter(
        lambda xml: xml['id'] == 'simple', body['data']
    ))[0]

    assert res.status_code == 200
    assert exit_req == {
        'id': 'simple',
        'version': '2018-02-19',
        'author': 'categulario',
        'date': '2018-02-19',
        'name': 'Simplest process ever',
        'description': 'A simple process that does nothing',
        'versions': ['2018-02-19'],
        'form_array': [
            {
                'ref': 'start_form',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'data',
                        'required': True,
                        'label': 'Info',
                    },
                ],
            },
        ],
    }


def test_list_processes_multiple(client):
    res = client.get('/v1/process')

    body = json.loads(res.data)
    exit_req = list(filter(
        lambda xml: xml['id'] == 'form-multiple', body['data']
    ))[0]

    assert res.status_code == 200
    assert exit_req == {
        'id': 'form-multiple',
        'version': '2018-04-08',
        'author': 'categulario',
        'date': '2018-04-08',
        'name': 'Con un formulario múltiple',
        'description':
            'Este proceso tiene un formulario que puede enviar muchas copias',
        'versions': ['2018-04-08'],
        'form_array': [
            {
                'ref': 'single-form',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'name',
                        'required': True,
                    },
                ],
            },
            {
                'ref': 'multiple-form',
                'multiple': '1-10',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'phone',
                        'required': True,
                    },
                ],
            },
        ],
    }


def test_read_process(client):
    res = client.get('/v1/process/oldest?version=2018-02-14')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['data']['name'] == 'Oldest process'
    assert data['data']['version'] == '2018-02-14'

    res = client.get('/v1/process/oldest')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['data']['name'] == 'Oldest process v2'
    assert data['data']['version'] == '2018-02-17'

    res = client.get('/v1/process/prueba')
    data = json.loads(res.data)
    assert res.status_code == 404
    assert data['errors'][0]['detail'] == 'prueba process does not exist'


def test_list_activities_requires(client):
    res = client.get('/v1/activity')

    assert res.status_code == 401


def test_list_activities(client):
    '''Given 4 activities, two for the current user and two for
    another, list only the two belonging to him or her'''
    juan = make_user('juan', 'Juan')
    other = make_user('other', 'Otero')

    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    exc_2 = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()
    exc_2.proxy.actors.add(juan)
    exc_2.save()
    res = client.get('/v1/activity', headers=make_auth(juan))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            exc_2.to_json(include=['*', 'execution']),
        ],
    }


def test_logs_activity(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid-node',
        },
    })

    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 50),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': '4g9lOdPKmRUf2',
        },
    })

    res = client.get('/v1/log/{}?node_id=mid-node'.format(EXECUTION_ID))

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [{
            'started_at': '2018-04-01T21:45:00+00:00',
            'finished_at': None,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': 'mid-node',
            },
        }],
    }


def test_task_list_requires_auth(client):
    res = client.get('/v1/task')

    assert res.status_code == 401
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }],
    }


def test_task_list(client):
    juan = make_user('user', 'User')

    pointer = make_pointer('simple.2018-02-19.xml', 'mid-node')
    juan.proxy.tasks.set([pointer])

    res = client.get('/v1/task', headers=make_auth(juan))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [pointer.to_json(include=['*', 'execution'])],
    }


def test_task_read_requires(client):
    # auth
    res = client.get('/v1/task/foo')

    assert res.status_code == 401

    # real pointer
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/foo', headers=make_auth(juan))

    assert res.status_code == 404

    # assigned task
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/{}'.format(ptr.id), headers=make_auth(juan))

    assert res.status_code == 403


def test_task_read(client):
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    juan = make_user('juan', 'Juan')
    juan.proxy.tasks.set([ptr])
    execution = ptr.proxy.execution.get()

    res = client.get('/v1/task/{}'.format(ptr.id), headers=make_auth(juan))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': {
            '_type': 'pointer',
            'id': ptr.id,
            'node_id': ptr.node_id,
            'node_type': 'action',
            'name': None,
            'description': None,
            'execution': {
                '_type': 'execution',
                'id': execution.id,
                'process_name': execution.process_name,
                'name': None,
                'description': None,
            },
            'form_array': [
                {
                    'ref': 'mid-form',
                    'inputs': [
                        {
                            'name': 'data',
                            'required': True,
                            'type': 'text',
                        },
                    ],
                },
            ],
        },
    }


def test_task_validation(client, mongo, config):
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    juan = make_user('juan', 'Juan')
    juan.proxy.tasks.add(ptr)
    execution = ptr.proxy.execution.get()

    state = Xml.load(config, 'validation').get_state()
    node = state['items']['start-node']

    node['state'] = 'valid'
    node['actors']['items']['juan'] = {
        '_type': 'actor',
        'state': 'valid',
        'user': {
            '_type': 'user',
            'identifier': 'juan',
            'fullname': None,
        },
        'forms': [{
            '_type': 'form',
            'ref': 'work',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'task': {
                        '_type': 'field',
                        'state': 'valid',
                        'label': 'task',
                        'value': 'Get some milk and eggs',
                    },
                },
                'item_order': ['task'],
            },
        }],
    }

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
    })

    res = client.get('/v1/task/{}'.format(ptr.id), headers=make_auth(juan))
    body = json.loads(res.data)['data']

    assert res.status_code == 200
    assert body == {
        '_type': 'pointer',
        'description': None,
        'execution': {
            '_type': 'execution',
            'description': None,
            'id': execution.id,
            'name': None,
            'process_name': execution.process_name,
        },
        'fields': [
            {
                '_type': 'field',
                'ref': 'start-node.juan.0:work.task',
                'label': 'task',
                'value': 'Get some milk and eggs',
            }
        ],
        'form_array': [],
        'id': ptr.id,
        'name': None,
        'node_id': ptr.node_id,
        'node_type': 'validation'
    }


def test_execution_has_node_info(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [
            {
                'ref': 'start_form',
                'data': {
                    'data': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 201

    exe = Execution.get_all()[0]
    ptr = Pointer.get_all()[0]

    assert exe.name == 'Simplest process ever started with: yes'
    assert exe.description == 'A simple process that does nothing'

    assert ptr.name == 'Primer paso'
    assert ptr.description == 'Resolver una tarea'


def test_log_has_node_info(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [
            {
                'ref': 'start_form',
                'data': {
                    'data': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 201

    body = json.loads(res.data)
    execution_id = body['data']['id']

    res = client.get('/v1/log/{}'.format(execution_id))
    body = json.loads(res.data)
    data = body['data'][0]

    assert data['node']['id'] == 'start-node'
    assert data['node']['name'] == 'Primer paso'
    assert data['node']['description'] == 'Resolver una tarea'

    assert data['execution']['id'] == execution_id
    assert data['execution']['name'] == \
        'Simplest process ever started with: yes'
    assert data['execution']['description'] == \
        'A simple process that does nothing'


def test_delete_process(config, client, mongo, mocker):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    p_0 = make_pointer('simple.2018-02-19.xml', 'mid-node')
    execution = p_0.proxy.execution.get()

    juan = make_user('juan', 'Juan')

    res = client.delete(
        '/v1/execution/{}'.format(execution.id),
        headers=make_auth(juan)
    )

    assert res.status_code == 202

    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'execution_id': execution.id,
        'command': 'cancel',
    }


def test_status_notfound(client):
    res = client.get('/v1/execution/doo')

    assert res.status_code == 404


def test_status(config, client, mongo):
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    execution = ptr.proxy.execution.get()

    mongo[config['EXECUTION_COLLECTION']].insert_one({
        'id': execution.id,
    })

    res = client.get('/v1/execution/{}'.format(execution.id))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': {
            'id': execution.id,
        },
    }


def test_execution_list(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        'status': 'ongoing',
    })

    res = client.get('/v1/execution')
    data = json.loads(res.data)

    assert res.status_code == 200
    assert data == {
        'data': [{
            'status': 'ongoing',
        }],
    }


def test_start_process_error_405(client, mongo, config):
    juan = make_user('juan', 'Juan')

    res = client.put('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data='{}')

    data = json.loads(res.data)
    assert res.status_code == 405
    assert data['errors'][0]['detail'] == \
        "The method is not allowed for the requested URL."


def test_node_statistics(client, mongo, config):
    def make_node_reg(process_id,  node_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': node_id,
            },
            'process_id': process_id
        }

    mongo[config["POINTER_COLLECTION"]].insert_many([
        make_node_reg(
            'simple.2018-02-19', 'test1',
            make_date(),
            make_date(2018, 5, 10, 4, 5, 6)
        ),
        make_node_reg(
            'simple.2018-02-19', 'test2',
            make_date(),
            make_date(2018, 5, 10, 6, 3, 3)
        ),
        make_node_reg(
            'simple.2018-02-19', 'test1',
            make_date(),
            make_date(2018, 5, 10, 8, 2, 9)
            ),
        make_node_reg(
            'simple.2018-02-19', 'test2',
            make_date(),
            make_date(2018, 5, 10, 3, 4, 5)
        ),
        make_node_reg(
            'simple.2018-02-19',
            'test2',
            make_date(),
            None
        ),
    ])

    res = client.get('/v1/process/{}/statistics'.format(
        'simple.2018-02-19'
    ))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            {
                'average': 540217.5,
                'max': 547329.0,
                'min': 533106.0,
                'node': 'test1',
                'process_id': 'simple.2018-02-19'
            },
            {
                'average': 534814.0,
                'max': 540183.0,
                'min': 529445.0,
                'node': 'test2',
                'process_id': 'simple.2018-02-19'
            },
        ],
    }


def test_process_statistics(client, mongo, config):
    def make_exec_reg(process_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'status': 'finished',
            'process': {
                'id': process_id,
                'version': 'v1',
            },
        }

    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        make_exec_reg('p1', make_date(), make_date(2018, 5, 10, 4, 5, 6)),
        make_exec_reg('p2', make_date(), make_date(2018, 5, 10, 10, 34, 32)),
        make_exec_reg('p1', make_date(), make_date(2018, 5, 11, 22, 41, 10)),
        make_exec_reg('p2', make_date(), make_date(2018, 6, 23, 8, 15, 1)),
    ])

    res = client.get('/v1/process/statistics')

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            {
                'average': 609788.0,
                'max': 686470.0,
                'min': 533106.0,
                'process': 'p1',
            },
            {
                'average': 2453086.5,
                'max': 4349701.0,
                'min': 556472.0,
                'process': 'p2',
            },

        ],
    }


def test_pagination_execution_log(client, mongo, config):
    def make_exec_reg(process_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'status': 'finished',
            'process': {
                'id': process_id,
                'version': 'v1',
            },
        }

    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        make_exec_reg('p1', make_date(), make_date(2018, 5, 10, 4, 5, 6)),
        make_exec_reg('p2', make_date(), make_date(2018, 5, 10, 10, 34, 32)),
        make_exec_reg('p3', make_date(), make_date(2018, 5, 11, 22, 41, 10)),
        make_exec_reg('p4', make_date(), make_date(2018, 6, 23, 8, 15, 1)),
        make_exec_reg('p5', make_date(), make_date(2018, 6, 11, 4, 5, 6)),
        make_exec_reg('p6', make_date(), make_date(2018, 6, 12, 5, 6, 32)),
        make_exec_reg('p7', make_date(), make_date(2018, 6, 13, 6, 7, 10)),
        make_exec_reg('p8', make_date(), make_date(2018, 6, 14, 7, 8, 1)),
    ])

    res = client.get('/v1/process/statistics?offset=2&limit=2')
    assert res.status_code == 200
    assert json.loads(res.data)['data'][0]["process"] == 'p3'
    assert json.loads(res.data)['data'][1]["process"] == 'p4'
    assert len(json.loads(res.data)['data']) == 2


def test_pagination_v1_log(client, mongo, config):

    def make_node_reg(process_id, node_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': node_id,
            },
            'process_id': process_id
        }

    mongo[config["POINTER_COLLECTION"]].insert_many([
        make_node_reg(
            'simple.2018-02-19', 'mid-node',
            make_date(),
            make_date(2018, 5, 20, 5, 5, 5)
        ),
        make_node_reg(
            'simple.2018-02-19', 'mid-node',
            make_date(),
            make_date(2018, 5, 21, 6, 6, 6)
            ),
        make_node_reg(
            'simple.2018-02-19', 'mid-node',
            make_date(),
            make_date(2018, 5, 22, 7, 7, 7)
        ),
        make_node_reg(
            'simple.2018-02-19',
            'mid-node',
            make_date(),
            make_date(2018, 5, 23, 8, 8, 8)
        ),
        make_node_reg(
            'simple.2018-02-19',
            'mid-node',
            make_date(),
            make_date(2018, 5, 24, 9, 9, 9)
        ),
    ])

    res = client.get(
        '/v1/log/{}?node_id=mid-node&offset=2&limit=2'.format(EXECUTION_ID)
    )
    assert json.loads(res.data)['data'][0]["finished_at"] == \
        '2018-05-22T07:07:07+00:00'
    assert json.loads(res.data)['data'][1]["finished_at"] == \
        '2018-05-23T08:08:08+00:00'
    assert len(json.loads(res.data)['data']) == 2
