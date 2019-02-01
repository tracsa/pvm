from datetime import datetime
from flask import json
from random import choice
from string import ascii_letters
import pika

from cacahuate.handler import Handler
from cacahuate.models import Pointer, Execution
from cacahuate.xml import Xml
from cacahuate.node import Form
from cacahuate.jsontypes import SortedMap, Map

from .utils import make_auth, make_pointer, make_user, make_date
from .utils import assert_near_date

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
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({}))

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
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
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
    juan = make_user('juan', 'Juan')
    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
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
    juan = make_user('juan', 'Juan')
    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'mid_node',
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
    juan = make_user('juan', 'Juan')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
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
    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
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
            'detail': "form count lower than expected for ref mid_form",
            'where': 'request.body.form_array',
        }],
    }


def test_continue_process(client, mocker, config):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
    manager.proxy.tasks.set([ptr])
    exc = ptr.proxy.execution.get()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(manager)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': ptr.node_id,
        'form_array': [
            {
                'ref': 'mid_form',
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
        'input': [Form.state_json('mid_form', [
            {
                "name": "data",
                "type": "text",
                "value": "yes",
                'label': 'data',
                'value_caption': 'yes',
                'state': 'valid',
                'hidden': False,
            },
        ])],
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
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
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
    assert mongo[config["POINTER_COLLECTION"]].count_documents({}) == 0


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

    assert ptr.node_id == 'start_node'

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
                'label': 'Info',
                'type': 'text',
                'value': 'yes',
                'value_caption': 'yes',
                'name': 'data',
                'state': 'valid',
                'hidden': False,
            },
        ])],
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
                'start_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'start_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': 'Primer paso',
                    'description': 'Resolver una tarea',
                },

                'mid_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'mid_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': 'Segundo paso',
                    'description': 'añadir información',
                },

                'final_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'final_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },
            },
            'item_order': [
                'start_node',
                'mid_node',
                'final_node',
            ],
        },
        'values': {},
        'actors': {},
    }


def test_validation_requirements(client):
    juan = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()
    juan.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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


def test_validation_approval(client, mocker, config):
    ''' the api for an approval '''
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()
    juan.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': 'approval_node',
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
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'accept',
            },
            {
                'name': 'comment',
                'value': 'I like the previous work',
            },
            {
                'name': 'inputs',
                'value': None,
            },
        ])],
    }


def test_validation_reject(client, mocker, config):
    ''' the api for a reject '''
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()
    juan.proxy.tasks.add(ptr)

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': ptr.node_id,
        'response': 'reject',
        'comment': 'I dont like it',
        'inputs': [{
            'ref': 'start_node.juan.0:work.task',
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
        'input': [Form.state_json('approval_node', [
            {
                'name': 'response',
                'value': 'reject',
            },
            {
                'name': 'comment',
                'value': 'I dont like it',
            },
            {
                'name': 'inputs',
                'value': [{
                    'ref': 'start_node.juan.0:work.task',
                }],
            },
        ])],
    }


def test_patch_requirements(client, mongo, config):
    juan = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })
    mongo[config['EXECUTION_COLLECTION']].update_one({
        'id': exc.id,
    }, {
        '$set': {
            'state.items.requester.actors': Map([{
                "_type": "actor",
                "forms": [{
                    '_type': 'form',
                    'state': 'valid',
                    'ref': 'exit_form',
                    'inputs': SortedMap([{
                        '_type': 'field',
                        'state': 'valid',
                        'value': 'yes',
                        'name': 'reason',
                    }], key='name').to_json(),
                }],
                "state": "valid",
                "user": {
                    "_type": "user",
                    "identifier": "__system__",
                    "fullname": "System"
                },
            }], key=lambda a: a['user']['identifier']).to_json(),
        },
    })

    # 'inputs' key is required
    res = client.patch('/v1/execution/{}'.format(exc.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'I dont like it',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [{
            'code': 'validation.required',
            'detail': '\'inputs\' is required',
            'where': 'request.body.inputs',
        }],
    }

    # all refs must exist
    res = client.patch('/v1/execution/{}'.format(exc.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'I dont like it',
        'inputs': [{
            'ref': 'node_id.form_ref.input_name',
        }],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'node node_id not found',
                'code': 'validation.invalid',
                'where': 'request.body.inputs.0.ref',
            },
        ],
    }

    # ref must pass validation if value present
    res = client.patch('/v1/execution/{}'.format(exc.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'I dont like it',
        'inputs': [{
            'ref': 'requester.exit_form.reason',
            'value': '',
        }],
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'value invalid: \'reason\' is required',
                'where': 'request.body.inputs.0.value',
                'code': 'validation.invalid',
            },
        ],
    }


def test_patch_just_invalidate(client, mongo, config, mocker):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })
    mongo[config['EXECUTION_COLLECTION']].update_one({
        'id': exc.id,
    }, {
        '$set': {
            'state.items.requester.actors': Map([{
                "_type": "actor",
                "forms": [{
                    '_type': 'form',
                    'state': 'valid',
                    'ref': 'exit_form',
                    'inputs': SortedMap([{
                        '_type': 'field',
                        'state': 'valid',
                        'value': 'yes',
                        'name': 'reason',
                    }], key='name').to_json(),
                }],
                "state": "valid",
                "user": {
                    "_type": "user",
                    "identifier": "juan",
                    "fullname": "System"
                },
            }], key=lambda a: a['user']['identifier']).to_json(),
        },
    })

    res = client.patch('/v1/execution/{}'.format(exc.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'a comment',
        'inputs': [{
            'ref': 'requester.exit_form.reason',
        }],
    }))

    assert res.status_code == 202

    # message is queued
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    json_message = {
        'command': 'patch',
        'execution_id': exc.id,
        'comment': 'a comment',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
        }],
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    body = json.loads(args['body'])
    assert body == json_message


def test_patch_set_value(client, mongo, config, mocker):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })
    mongo[config['EXECUTION_COLLECTION']].update_one({
        'id': exc.id,
    }, {
        '$set': {
            'state.items.requester.actors': Map([{
                "_type": "actor",
                "forms": [{
                    '_type': 'form',
                    'state': 'valid',
                    'ref': 'exit_form',
                    'inputs': SortedMap([{
                        '_type': 'field',
                        'state': 'valid',
                        'value': 'yes',
                        'name': 'reason',
                    }], key='name').to_json(),
                }],
                "state": "valid",
                "user": {
                    "_type": "user",
                    "identifier": "juan",
                    "fullname": "System"
                },
            }], key=lambda a: a['user']['identifier']).to_json(),
        },
    })

    res = client.patch('/v1/execution/{}'.format(exc.id), headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'comment': 'a comment',
        'inputs': [{
            'ref': 'requester.exit_form.reason',
            'value': 'the reason',
        }],
    }))

    assert res.status_code == 202

    # message is queued
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    json_message = {
        'command': 'patch',
        'execution_id': exc.id,
        'comment': 'a comment',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
            'value': 'the reason',
            'value_caption': 'the reason',
        }],
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    body = json.loads(args['body'])
    assert body == json_message


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
                'ref': 'single_form',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'name',
                        'required': True,
                        'label': 'Single Form',
                    },
                ],
            },
            {
                'ref': 'multiple_form',
                'multiple': '1-10',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'phone',
                        'required': True,
                        'label': 'Multi Form',
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

    Execution(
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


def test_mix_data(mongo, client, config):
    juan = make_user('user', 'User')

    # Create pointers

    ptr_01 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_02 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_03 = make_pointer('exit_request.2018-03-20.xml', 'requester')
    ptr_04 = make_pointer('validation.2018-05-09.xml', 'approval_node')

    juan.proxy.tasks.set([ptr_01, ptr_02, ptr_04])

    ptr_01_json = ptr_01.to_json(include=['*', 'execution'])
    ptr_02_json = ptr_02.to_json(include=['*', 'execution'])
    ptr_03_json = ptr_03.to_json(include=['*', 'execution'])
    ptr_04_json = ptr_04.to_json(include=['*', 'execution'])

    # set started_at to ptrs
    ptr_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    ptr_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    ptr_03_json['started_at'] = '2018-04-01T21:47:00+00:00'
    ptr_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    # Pointer collection
    mongo[config["POINTER_COLLECTION"]].insert_many([
        ptr_01_json.copy(),
        ptr_02_json.copy(),
        ptr_03_json.copy(),
        ptr_04_json.copy(),
    ])

    # Create executions

    exec_01 = ptr_01.proxy.execution.get()
    exec_02 = ptr_02.proxy.execution.get()
    exec_03 = ptr_03.proxy.execution.get()
    exec_04 = ptr_04.proxy.execution.get()

    juan.proxy.activities.set([exec_01, exec_02, exec_04])

    exec_01_json = exec_01.to_json()
    exec_02_json = exec_02.to_json()
    exec_03_json = exec_03.to_json()
    exec_04_json = exec_04.to_json()

    # set started_at to ptrs
    exec_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    exec_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    exec_03_json['started_at'] = '2018-04-01T21:47:00+00:00'
    exec_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    # Execution collection
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        exec_01_json.copy(),
        exec_02_json.copy(),
        exec_03_json.copy(),
        exec_04_json.copy(),
    ])

    res = client.get('/v1/inbox')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            ptr_04_json,
            ptr_03_json,
            ptr_02_json,
            ptr_01_json,
            exec_04_json,
            exec_03_json,
            exec_02_json,
            exec_01_json,
        ],
    }


def test_mix_data_filter_user(mongo, client, config):
    juan = make_user('user', 'User')

    # Create pointers

    ptr_01 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_02 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_03 = make_pointer('exit_request.2018-03-20.xml', 'requester')
    ptr_04 = make_pointer('validation.2018-05-09.xml', 'approval_node')

    juan.proxy.tasks.set([ptr_01, ptr_02, ptr_04])

    ptr_01_json = ptr_01.to_json(include=['*', 'execution'])
    ptr_02_json = ptr_02.to_json(include=['*', 'execution'])
    ptr_03_json = ptr_03.to_json(include=['*', 'execution'])
    ptr_04_json = ptr_04.to_json(include=['*', 'execution'])

    # set started_at to ptrs
    ptr_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    ptr_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    ptr_03_json['started_at'] = '2018-04-01T21:47:00+00:00'
    ptr_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    # Pointer collection
    mongo[config["POINTER_COLLECTION"]].insert_many([
        ptr_01_json.copy(),
        ptr_02_json.copy(),
        ptr_03_json.copy(),
        ptr_04_json.copy(),
    ])

    # Create executions

    exec_01 = ptr_01.proxy.execution.get()
    exec_02 = ptr_02.proxy.execution.get()
    exec_03 = ptr_03.proxy.execution.get()
    exec_04 = ptr_04.proxy.execution.get()

    juan.proxy.activities.set([exec_01, exec_02, exec_04])

    exec_01_json = exec_01.to_json()
    exec_02_json = exec_02.to_json()
    exec_03_json = exec_03.to_json()
    exec_04_json = exec_04.to_json()

    # set started_at to ptrs
    exec_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    exec_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    exec_03_json['started_at'] = '2018-04-01T21:47:00+00:00'
    exec_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    # Execution collection
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        exec_01_json.copy(),
        exec_02_json.copy(),
        exec_03_json.copy(),
        exec_04_json.copy(),
    ])

    res = client.get(f'/v1/inbox?user_identifier={juan.identifier}')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            ptr_04_json,
            ptr_02_json,
            ptr_01_json,
            exec_04_json,
            exec_02_json,
            exec_01_json,
        ],
    }


def test_logs_all(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_many([
        {
            'started_at': datetime(2018, 4, 1, 21, 45),
            'finished_at': None,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': 'first_node',
            },
        },
        {
            'started_at': datetime(2018, 4, 1, 21, 46),
            'finished_at': None,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': 'mid_node',
            },
        },
        {
            'started_at': datetime(2018, 4, 1, 21, 45),
            'finished_at': None,
            'execution': {
                'id': 'xxxxffff',
            },
            'node': {
                'id': 'mid_node',
            },
        },
        {
            'started_at': datetime(2018, 4, 1, 21, 44),
            'finished_at': None,
            'execution': {
                'id': EXECUTION_ID,
            },
            'node': {
                'id': 'another_node',
            },
        },
    ])

    res = client.get('/v1/log')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            {
                'started_at': '2018-04-01T21:46:00+00:00',
                'finished_at': None,
                'execution': {
                    'id': EXECUTION_ID,
                },
                'node': {
                    'id': 'mid_node',
                },
            },
            {
                'started_at': '2018-04-01T21:45:00+00:00',
                'finished_at': None,
                'execution': {
                    'id': 'xxxxffff',
                },
                'node': {
                    'id': 'mid_node',
                },
            },
        ],
    }


def test_logs_filter_user(mongo, client, config):
    juan = make_user('user', 'User')

    ptr_01 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_02 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_03 = make_pointer('exit_request.2018-03-20.xml', 'requester')
    ptr_04 = make_pointer('validation.2018-05-09.xml', 'approval_node')

    juan.proxy.tasks.set([ptr_01, ptr_02, ptr_04])

    ptr_01_json = ptr_01.to_json(include=['*', 'execution'])
    ptr_02_json = ptr_02.to_json(include=['*', 'execution'])
    ptr_03_json = ptr_03.to_json(include=['*', 'execution'])
    ptr_04_json = ptr_04.to_json(include=['*', 'execution'])

    # set started_at to ptrs
    ptr_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    ptr_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    ptr_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    mongo[config["POINTER_COLLECTION"]].insert_many([
        ptr_01_json.copy(),
        ptr_02_json.copy(),
        ptr_03_json.copy(),
        ptr_04_json.copy(),
    ])

    res = client.get('/v1/log?user_identifier={}'.format(juan.identifier))

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            ptr_04_json,
            ptr_02_json,
            ptr_01_json,
        ],
    }


def test_logs_filter_user_invalid(mongo, client, config):
    ptr_01 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_02 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_03 = make_pointer('exit_request.2018-03-20.xml', 'requester')
    ptr_04 = make_pointer('validation.2018-05-09.xml', 'approval_node')

    mongo[config["POINTER_COLLECTION"]].insert_many([
        ptr_01.to_json(include=['*', 'execution']),
        ptr_02.to_json(include=['*', 'execution']),
        ptr_03.to_json(include=['*', 'execution']),
        ptr_04.to_json(include=['*', 'execution']),
    ])

    res = client.get('/v1/log?user_identifier=foo')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [],
    }


def test_logs_filter_key_valid(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid_node',
        },
        'one_key': 'foo',
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
        'one_key': 'bar',
    })

    res = client.get('/v1/log?one_key=foo')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            {
                'started_at': '2018-04-01T21:45:00+00:00',
                'finished_at': None,
                'execution': {
                    'id': EXECUTION_ID,
                },
                'node': {
                    'id': 'mid_node',
                },
                'one_key': 'foo',
            },
        ],
    }


def test_logs_filter_key_invalid(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid_node',
        },
    })

    res = client.get('/v1/log?limit=foo')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            {
                'started_at': '2018-04-01T21:45:00+00:00',
                'finished_at': None,
                'execution': {
                    'id': EXECUTION_ID,
                },
                'node': {
                    'id': 'mid_node',
                },
            },
        ],
    }


def test_logs_filter_value_invalid(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid_node',
        },
        'one_key': 'bar',
    })

    res = client.get('/v1/log?one_key=foo')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [],
    }


def test_logs_activity(mongo, client, config):
    mongo[config["POINTER_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid_node',
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

    res = client.get('/v1/log/{}?node_id=mid_node'.format(EXECUTION_ID))

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
                'id': 'mid_node',
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

    pointer = make_pointer('simple.2018-02-19.xml', 'mid_node')
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
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/{}'.format(ptr.id), headers=make_auth(juan))

    assert res.status_code == 403


def test_task_read(client, config, mongo):
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
    juan = make_user('juan', 'Juan')
    juan.proxy.tasks.set([ptr])
    execution = ptr.proxy.execution.get()

    state = Xml.load(config, 'simple.2018-02-19').get_state()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': state,
    })

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
                    'ref': 'mid_form',
                    'inputs': [
                        {
                            'name': 'data',
                            'required': True,
                            'type': 'text',
                            'label': 'data',
                        },
                    ],
                },
            ],
        },
    }


def test_task_validation(client, mongo, config):
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    juan = make_user('juan', 'Juan')
    juan.proxy.tasks.add(ptr)
    execution = ptr.proxy.execution.get()

    state = Xml.load(config, 'validation.2018-05-09').get_state()
    node = state['items']['start_node']

    node['state'] = 'valid'
    node['actors']['items']['juan'] = {
        '_type': 'actor',
        'state': 'valid',
        'user': {
            '_type': 'user',
            'identifier': 'juan',
            'fullname': None,
        },
        'forms': [Form.state_json('work', [
            {
                '_type': 'field',
                'state': 'valid',
                'label': 'task',
                'name': 'task',
                'value': 'Get some milk and eggs',
            },
        ])],
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
                'ref': 'start_node.juan.0:work.task',
                'label': 'task',
                'name': 'task',
                'value': 'Get some milk and eggs',
            }
        ],
        'form_array': [],
        'id': ptr.id,
        'name': None,
        'node_id': ptr.node_id,
        'node_type': 'validation'
    }


def test_task_with_prev_work(client, config, mongo):
    ptr = make_pointer('validation-multiform.2018-05-22.xml', 'start_node')
    juan = make_user('juan', 'Juan')
    juan.proxy.tasks.add(ptr)
    execution = ptr.proxy.execution.get()

    state = Xml.load(config, 'validation-multiform.2018-05-22').get_state()
    node = state['items']['start_node']

    prev_work = [Form.state_json('set', [
        {'_type': 'field', 'name': 'A', 'value': 'a1', 'state': 'valid'},
        {'_type': 'field', 'name': 'B', 'value': 'b1', 'state': 'valid'},
        {'_type': 'field', 'name': 'C', 'value': 'c1', 'state': 'invalid'},
        {'_type': 'field', 'name': 'D', 'value': 'd1', 'state': 'valid'},
    ]), Form.state_json('set', [
        {'_type': 'field', 'name': 'A', 'value': 'a2', 'state': 'valid'},
        {'_type': 'field', 'name': 'B', 'value': 'b2', 'state': 'valid'},
        {'_type': 'field', 'name': 'C', 'value': 'c2', 'state': 'valid'},
        {'_type': 'field', 'name': 'D', 'value': 'd2', 'state': 'valid'},
    ])]

    node['state'] = 'valid'
    node['actors']['items']['juan'] = {
        '_type': 'actor',
        'state': 'valid',
        'user': {
            '_type': 'user',
            'identifier': 'juan',
            'fullname': None,
        },
        'forms': prev_work,
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
        'form_array': [{
            'inputs': [
                {'label': 'Value A', 'name': 'A', 'type': 'text'},
                {'label': 'Value B', 'name': 'B', 'type': 'text'},
                {'label': 'Value C', 'name': 'C', 'type': 'text'},
                {'label': 'Value D', 'name': 'D', 'type': 'text'}
            ],
            'multiple': '1-5',
            'ref': 'set'
        }],
        'id': ptr.id,
        'name': None,
        'node_id': ptr.node_id,
        'node_type': 'action',
        'prev_work': node['actors']['items']['juan']['forms'],
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

    assert data['node']['id'] == 'start_node'
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

    p_0 = make_pointer('simple.2018-02-19.xml', 'mid_node')
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
    ptr = make_pointer('simple.2018-02-19.xml', 'mid_node')
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


def test_execution_filter_key_valid(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': 1,
            'one_key': 'foo',
        },
        {
            'id': 2,
            'another_key': 'var',
        },
        {
            'id': 3,
            'one_key': 'foo',
        },
        {
            'id': 4,
            'one_key': 'zas',
        },
    ])

    res = client.get('/v1/execution?one_key=foo')
    data = json.loads(res.data)

    assert res.status_code == 200
    assert data == {
        'data': [
            {
                'id': 1,
                'one_key': 'foo',
            },
            {
                'id': 3,
                'one_key': 'foo',
            }
        ],
    }


def test_execution_filter_key_invalid(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': 1,
            'limit': 'bar',
        },
    ])

    res = client.get('/v1/execution?limit=foo')
    data = json.loads(res.data)

    assert res.status_code == 200
    assert data == {
        'data': [
            {
                'id': 1,
                'limit': 'bar',
            },
        ],
    }


def test_execution_filter_user(mongo, client, config):
    juan = make_user('user', 'User')

    ptr_01 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_02 = make_pointer('simple.2018-02-19.xml', 'mid_node')
    ptr_03 = make_pointer('exit_request.2018-03-20.xml', 'requester')
    ptr_04 = make_pointer('validation.2018-05-09.xml', 'approval_node')

    exec_01 = ptr_01.proxy.execution.get()
    exec_02 = ptr_02.proxy.execution.get()
    exec_03 = ptr_03.proxy.execution.get()
    exec_04 = ptr_04.proxy.execution.get()

    juan.proxy.activities.set([exec_01, exec_02, exec_04])

    exec_01_json = exec_01.to_json()
    exec_02_json = exec_02.to_json()
    exec_03_json = exec_03.to_json()
    exec_04_json = exec_04.to_json()

    # set started_at to ptrs
    exec_01_json['started_at'] = '2018-04-01T21:45:00+00:00'
    exec_02_json['started_at'] = '2018-04-01T21:46:00+00:00'
    exec_04_json['started_at'] = '2018-04-01T21:48:00+00:00'

    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        exec_01_json.copy(),
        exec_02_json.copy(),
        exec_03_json.copy(),
        exec_04_json.copy(),
    ])

    res = client.get(f'/v1/execution?user_identifier={juan.identifier}')

    ans = json.loads(res.data)

    assert res.status_code == 200
    assert ans == {
        "data": [
            exec_04_json,
            exec_02_json,
            exec_01_json,
        ],
    }


def test_execution_filter_value_invalid(client, mongo, config):

    res = client.get('/v1/execution?one_key=foo')
    data = json.loads(res.data)

    assert res.status_code == 200
    assert data == {
        'data': [],
    }


def test_add_user(client, mocker, config, mongo):
    # variables: users
    juan = make_user('juan', 'Juan')
    luis = make_user('luis', 'Luis')

    # variables: pointer and execution
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })

    pointer = ptr.to_json()
    pointer['execution'] = exc.to_json()
    mongo[config["POINTER_COLLECTION"]].insert_one(pointer)

    # user has no task assigned
    assert luis.proxy.tasks.count() == 0

    # add the user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'approval_node',
        })
    )
    # successful post
    assert res.status_code == 200

    # user has one task assigned
    assert luis.proxy.tasks.count() == 1

    # test notified_users (log)
    res = client.get(
        '/v1/log/{}'.format(exc.id),
    )

    notified_users = json.loads(res.data)['data'][0]['notified_users']
    assert res.status_code == 200
    assert notified_users == [luis.to_json()]


def test_add_user_new(client, mocker, config, mongo):
    # variables: users
    juan = make_user('juan', 'Juan')
    luis = make_user('luis', 'Luis')
    beto = make_user('beto', 'Beto')

    # variables: pointer and execution
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })

    pointer = ptr.to_json()
    pointer['execution'] = exc.to_json()
    mongo[config["POINTER_COLLECTION"]].insert_one(pointer)

    # user has no task assigned
    assert luis.proxy.tasks.count() == 0
    assert beto.proxy.tasks.count() == 0

    # add the user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'approval_node',
        })
    )
    # successful post
    assert res.status_code == 200

    # user has one task assigned
    assert luis.proxy.tasks.count() == 1

    # test notified_users (log)
    res = client.get(
        '/v1/log/{}'.format(exc.id),
    )

    notified_users = json.loads(res.data)['data'][0]['notified_users']
    assert res.status_code == 200
    assert notified_users == [luis.to_json()]

    # add the second user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'beto',
            'node_id': 'approval_node',
        })
    )
    # successful post
    assert res.status_code == 200

    # user has one task assigned
    assert beto.proxy.tasks.count() == 1

    # test notified_users (log)
    res = client.get(
        '/v1/log/{}'.format(exc.id),
    )

    notified_users = json.loads(res.data)['data'][0]['notified_users']
    assert res.status_code == 200
    assert notified_users == [luis.to_json(), beto.to_json()]


def test_add_user_duplicate(client, mocker, config, mongo):
    # variables: users
    juan = make_user('juan', 'Juan')
    luis = make_user('luis', 'Luis')

    # variables: pointer and execution
    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })

    pointer = ptr.to_json()
    pointer['execution'] = exc.to_json()
    mongo[config["POINTER_COLLECTION"]].insert_one(pointer)

    # user has no task assigned
    assert luis.proxy.tasks.count() == 0

    # add the user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'approval_node',
        })
    )
    # successful post
    assert res.status_code == 200

    # user has one task assigned
    assert luis.proxy.tasks.count() == 1

    # test notified_users (log)
    res = client.get(
        '/v1/log/{}'.format(exc.id),
    )

    notified_users = json.loads(res.data)['data'][0]['notified_users']
    assert res.status_code == 200
    assert notified_users == [luis.to_json()]

    # add the second user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'approval_node',
        })
    )
    # successful post
    assert res.status_code == 200

    # user has one task assigned
    assert luis.proxy.tasks.count() == 1

    # test notified_users (log)
    res = client.get(
        '/v1/log/{}'.format(exc.id),
    )

    notified_users = json.loads(res.data)['data'][0]['notified_users']
    assert res.status_code == 200
    assert notified_users == [luis.to_json()]


def test_add_user_requirements_id(client, mocker, config, mongo):
    juan = make_user('juan', 'Juan')

    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })

    # try add the user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'approval_node',
        })
    )

    # post requires valid user id
    assert res.status_code == 400


def test_add_user_requirements_node(client, mocker, config, mongo):
    juan = make_user('juan', 'Juan')
    make_user('luis', 'Luis')

    ptr = make_pointer('validation.2018-05-09.xml', 'approval_node')
    exc = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': exc.id,
        'state': Xml.load(config, exc.process_name, direct=True).get_state(),
    })

    # try add the user
    res = client.put(
        '/v1/execution/{}/user'.format(exc.id),
        headers={
            **{'Content-Type': 'application/json'},
            **make_auth(juan)},
        data=json.dumps({
            'identifier': 'luis',
            'node_id': 'final_node',
        })
    )
    # post requires valid living node
    assert res.status_code == 400


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
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 20, 5, 5, 5),
            make_date(2018, 5, 20, 5, 5, 5)
        ),
        make_node_reg(
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 21, 6, 6, 6),
            make_date(2018, 5, 21, 6, 6, 6)
            ),
        make_node_reg(
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 22, 7, 7, 7),
            make_date(2018, 5, 22, 7, 7, 7)
        ),
        make_node_reg(
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 23, 8, 8, 8),
            make_date(2018, 5, 23, 8, 8, 8)
        ),
        make_node_reg(
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 24, 9, 9, 9),
            make_date(2018, 5, 24, 9, 9, 9)
        ),
    ])

    res = client.get(
        '/v1/log/{}?node_id=mid_node&offset=2&limit=2'.format(EXECUTION_ID)
    )
    assert json.loads(res.data)['data'][0]["finished_at"] == \
        '2018-05-22T07:07:07+00:00'
    assert json.loads(res.data)['data'][1]["finished_at"] == \
        '2018-05-21T06:06:06+00:00'
    assert len(json.loads(res.data)['data']) == 2


def test_pagination_v1_log_all(client, mongo, config):

    def make_node_reg(exec_id, process_id, node_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'execution': {
                'id': exec_id,
            },
            'node': {
                'id': node_id,
            },
            'process_id': process_id
        }

    mongo[config["POINTER_COLLECTION"]].insert_many([
        make_node_reg(
            'aaaaaaaa',
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 20, 5, 5, 5),
            make_date(2018, 5, 20, 5, 5, 5)
        ),
        make_node_reg(
            'bbbbbbbb',
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 21, 6, 6, 6),
            make_date(2018, 5, 21, 6, 6, 6)
            ),
        make_node_reg(
            'cccccccc',
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 22, 7, 7, 7),
            make_date(2018, 5, 22, 7, 7, 7)
        ),
        make_node_reg(
            'dddddddd',
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 23, 8, 8, 8),
            make_date(2018, 5, 23, 8, 8, 8)
        ),
        make_node_reg(
            'eeeeeeee',
            'simple.2018-02-19', 'mid_node',
            make_date(2018, 5, 24, 9, 9, 9),
            make_date(2018, 5, 24, 9, 9, 9)
        ),
    ])

    res = client.get(
        '/v1/log?offset=2&limit=2'
    )
    assert json.loads(res.data)['data'][0]["started_at"] == \
        '2018-05-22T07:07:07+00:00'
    assert json.loads(res.data)['data'][1]["started_at"] == \
        '2018-05-21T06:06:06+00:00'
    assert len(json.loads(res.data)['data']) == 2


def test_name_with_if(client, mongo, config):
    xml = Xml.load(config, 'pollo')
    assert xml.name == 'pollo.2018-05-20.xml'


def test_get_xml(client):

    res = client.get('/v1/process/validation-multiform.xml')
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'text/xml; charset=utf-8'
    assert res.data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
