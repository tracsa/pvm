from flask import json
import pytest
import case_conversion
import pika

from pvm.models import Execution, Pointer
from pvm.handler import Handler

@pytest.mark.skip
def test_continue_process_requires(client):
    res = client.post('/v1/pointer')

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'execution_id is required',
                'i18n': 'errors.execution_id.required',
                'field': 'execution_id',
            },
            {
                'detail': 'node_id is required',
                'i18n': 'errors.node_id.required',
                'field': 'node_id',
            },
        ],
    }

@pytest.mark.skip
def test_continue_process_asks_living_objects(client):
    ''' the app must validate that the ids sent are real objects '''
    res = client.post('/v1/pointer', data={
        'execution_id': 'verde',
        'node_id': 'nada',
    })

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'execution_id is not valid',
                'i18n': 'errors.execution_id.invalid',
                'field': 'execution_id',
            },
        ],
    }

@pytest.mark.skip
def test_continue_process_requires_living_pointer(client):
    exc = Execution(
        process_name = 'decision_2018-02-27',
    ).save()
    res = client.post('/v1/pointer', data={
        'execution_id': exc.id,
        'node_id': '57TJ0V3nur6m7wvv',
    })

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'node_id does not have a live pointer',
                'i18n': 'errors.node_id.no_live_pointer',
                'field': 'node_id',
            },
        ],
    }

@pytest.mark.skip
def test_can_continue_process(client, models, mocker):
    exc = Execution(
        process_name = 'decision_2018-02-27',
    ).save()
    ptr = Pointer(node_id='57TJ0V3nur6m7wvv').save()
    ptr.proxy.execution.set(exc)

    mocker.patch('pika.adapters.blocking_connection.BlockingChannel.basic_publish')

    res = client.post('/v1/pointer', data={
        'execution_id': exc.id,
        'node_id': '57TJ0V3nur6m7wvv',
    })

    pika.adapters.blocking_connection.BlockingChannel.basic_publish.assert_called_once_with()

    assert res.status_code == 202
    assert json.loads(res.data) == {
        'data': {
            'detail': 'accepted',
        },
    }

@pytest.mark.skip
def test_can_query_process_status(client):
    res = client.get('/v1/node/{}')

    assert res.status_code == 200
    assert res.data == {
        'data': [
            {
                '_type': 'node',
                'id': '',
                'data': {},
            },
        ]
    }

def test_process_start_simple_requires(client, models):
    # we need the name of the process to start
    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data='{}')

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'process_name is required',
                'where': 'request.body.process_name',
            },
        ],
    }

    # we need an existing process to start
    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
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

    # we need a process with a start node
    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
        'process_name': 'nostart',
    }))

    assert res.status_code == 422
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'nostart process does not have a start node, thus cannot be started',
                'where': 'request.body.process_name',
            },
        ],
    }

def test_process_start_simple(client, models, mocker, config):
    mocker.patch('pika.adapters.blocking_connection.BlockingChannel.basic_publish')

    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
        'process_name': 'simple',
    }))

    assert res.status_code == 201

    exc = Execution.get_all()[0]

    assert exc.process_name == 'simple_2018-02-19.xml'

    ptr = exc.proxy.pointers.get()[0]

    assert ptr.node_id == 'gYcj0XjbgjSO'

    pika.adapters.blocking_connection.BlockingChannel.basic_publish.assert_called_once()

    args =  pika.adapters.blocking_connection.BlockingChannel.basic_publish.call_args[1]

    json_message = {
        'command': 'step',
        'process': exc.process_name,
        'pointer_id': ptr.id,
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == json_message

    handler = Handler(config)

    execution, pointer, xmliter, current_node = handler.recover_step(json_message)

    assert execution.id == exc.id
    assert pointer.id == ptr.id

def test_exit_request_requirements(client, models, mocker):
    mocker.patch('pika.adapters.blocking_connection.BlockingChannel.basic_publish')

    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
        'process_name': 'exit_request',
    }))

    assert res.status_code == 401
    assert 'WWW-Authenticate' in res.headers
    assert res.headers['WWW-Authenticate'] == 'Basic realm="User Visible Realm"'
    assert json.loads(res.data) == {
        'errors': [{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }],
    }
