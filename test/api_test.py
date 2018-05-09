from datetime import datetime
from datetime import timedelta
from flask import json, jsonify
import pika
import pytest
from cacahuate.handler import Handler
from cacahuate.models import Pointer, Execution, Activity, Questionaire

from .utils import make_auth, make_activity, make_pointer, make_user, make_date

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
                'detail': 'execution_id is required',
                'code': 'validation.required',
                'where': 'request.body.execution_id',
            },
            {
                'detail': 'node_id is required',
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
    act = Activity(ref='requester').save()
    act.proxy.user.set(juan)

    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    manager.proxy.tasks.set([ptr])

    act.proxy.execution.set(ptr.proxy.execution.get())

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

    act = make_activity('requester', juan, ptr.proxy.execution.get())

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

    # user is attached

    assert exc.proxy.actors.count() == 2

    activity = next(exc.proxy.actors.q().filter(ref='mid-node'))

    assert activity.ref == 'mid-node'
    assert activity.proxy.user.get() == manager

    # form is attached
    forms = exc.proxy.forms.get()

    assert len(forms) == 1

    form = forms[0]

    assert form.ref == 'mid-form'
    assert form.data == {
        'data': 'yes',
    }

    # rabbit is called
    pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.assert_called_once()

    args = pika.adapters.blocking_connection.BlockingChannel.\
        basic_publish.call_args[1]

    json_message = {
        'command': 'step',
        'pointer_id': ptr.id,
        'actor': {
            'ref': 'mid-node',
            'user': {
                'identifier': 'juan_manager',
                'human_name': 'Juanote',
            },
            'forms': [
                {
                    'ref': 'mid-form',
                    'form': [
                        {
                            "name": "data",
                            "type": "text",
                            "value": "yes",
                            "required": True,
                            'default': None,
                            'label': 'data',
                        }
                    ],
                    'data': {
                        'data': 'yes',
                    },
                },
            ],
        },
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == json_message

    # makes a useful call for the handler
    handler = Handler(config)

    execution, pointer, xmliter, current_node, *rest = \
        handler.recover_step(json_message)

    assert execution.id == exc.id
    assert pointer.id == ptr.id


def test_start_process_simple_requires(client, mongo, config):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data='{}')

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'process_name is required',
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
    assert mongo[config["MONGO_HISTORY_COLLECTION"]].count() == 0
    assert Activity.count() == 0
    assert Questionaire.count() == 0


def test_start_process_simple(client, mocker, config, mongo):
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
            'ref': 'start-form',
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
        'process': exc.process_name,
        'pointer_id': ptr.id,
    }

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == json_message

    handler = Handler(config)

    execution, pointer, xmliter, current_node, *rest = \
        handler.recover_step(json_message)

    assert execution.id == exc.id
    assert pointer.id == ptr.id

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert (reg['started_at'] - datetime.now()).total_seconds() < 2
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == exc.id
    assert reg['node']['id'] == ptr.node_id
    assert reg['state'] == {
        'forms': [{
            'ref': 'start-form',
            'data': {
                'data': 'yes',
            },
        }],
        'actors': [{
            'ref': 'start-node',
            'user_id': juan.id,
        }],
    }

    reg2 = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg2['id'] == exc.id
    assert reg2['status'] == 'ongoing'


def test_simple_requirements(client):
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
    assert Activity.count() == 0

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
            'detail': "form count lower than expected for ref start-form",
            'where': 'request.body.form_array',
        }],
    }

    assert Execution.count() == 0
    assert Activity.count() == 0


def test_simple_start(client, mocker, mongo, config):
    user = make_user('juan', 'Juan')

    assert Execution.count() == 0
    assert Activity.count() == 0

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [
            {
                'ref': 'start-form',
                'data': {
                    'data': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 201

    exc = Execution.get_all()[0]

    assert json.loads(res.data) == {
        'data': exc.to_json(),
    }
    # user is attached
    actors = exc.proxy.actors.get()

    assert len(actors) == 1

    activity = actors[0]

    assert activity.ref == 'start-node'
    assert activity.proxy.user.get() == user

    # form is attached
    forms = exc.proxy.forms.get()

    assert len(forms) == 1

    form = forms[0]

    assert form.ref == 'start-form'
    assert form.data == {
        'data': 'yes',
    }

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['state'] == {
        'forms': [{
            'ref': 'start-form',
            'data': {
                'data': 'yes',
            },
        }],
        'actors': [
            {
                'ref': 'start-node',
                'user_id': user.id,
            }
        ],
    }


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
                'ref': 'start-form',
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
                'multiple': 'multiple',
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

    act = make_activity('requester', juan, exc)
    act2 = make_activity('some', other, exc)

    res = client.get('/v1/activity', headers=make_auth(juan))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            act.to_json(embed=['execution']),
        ],
    }


def test_activity_requires(client):
    # validate user authentication wrong
    res = client.get('/v1/activity/1')
    assert res.status_code == 401


def test_activity_wrong_activity(client):
    # validate user authentication correct but bad activity
    juan = make_user('juan', 'Juan')
    other = make_user('other', 'Otero')

    exc = Execution(
        process_name='simple.2018-02-19.xml',
    ).save()

    act = make_activity('requester', juan, exc)
    act2 = make_activity('some', other, exc)

    res = client.get(
        '/v1/activity/{}'.format(act2.id),
        headers=make_auth(juan)
    )

    assert res.status_code == 403


def test_activity(client):
    # validate user authentication correct with correct activity
    juan = make_user('juan', 'Juan')

    act = Activity(ref='requester').save()
    act.proxy.user.set(juan)

    res2 = client.get(
        '/v1/activity/{}'.format(act.id),
        headers=make_auth(juan)
    )

    assert res2.status_code == 200
    assert json.loads(res2.data) == {
        'data': act.to_json(embed=['execution']),
    }


def test_logs_activity(mongo, client, config):
    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': EXECUTION_ID,
        },
        'node': {
            'id': 'mid-node',
        },
    })

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
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
        'data': [pointer.to_json(embed=['execution'])],
    }


def test_task_read_requires_auth(client):
    res = client.get('/v1/task/foo')

    assert res.status_code == 401


def test_task_read_requires_real_pointer(client):
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/foo', headers=make_auth(juan))

    assert res.status_code == 404


def test_task_read_requires_assigned_task(client):
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


def test_execution_has_node_info(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [
            {
                'ref': 'start-form',
                'data': {
                    'data': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 201

    exe = Execution.get_all()[0]
    ptr = Pointer.get_all()[0]

    assert exe.name == 'Simplest process ever'
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
                'ref': 'start-form',
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
    assert data['execution']['name'] == 'Simplest process ever'
    assert data['execution']['description'] == \
        'A simple process that does nothing'


def test_log_has_form_input_data(client):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [
            {
                'ref': 'start-form',
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

    assert data['actors'][0]['forms'][0]['form'] == [
        {
            "label": "Info",
            "name": "data",
            "type": "text",
            "value": "yes",
            "required": True,
            'default': None,
        },
    ]


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

    mongo[config['MONGO_EXECUTION_COLLECTION']].insert_one({
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
    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
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
    def make_node_reg(node_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'execution': {
                'id': config['EXECUTION_ID_TEST'],
            },
            'node': {
                'id': node_id,
            },
        }

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_many([
        make_node_reg('test1', make_date(), make_date(2018, 5, 10, 4, 5, 6)),
        make_node_reg('test2', make_date(), make_date(2018, 5, 10, 6, 3, 3)),
        make_node_reg('test1', make_date(), make_date(2018, 5, 10, 8, 2, 9)),
        make_node_reg('test2', make_date(), make_date(2018, 5, 10, 3, 4, 5)),
        make_node_reg('test2', make_date(), None),
    ])

    res = client.get('/v1/process/{}/statistics'.format(
        config['EXECUTION_ID_TEST']
    ))
    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [
            {
                'average': 540217.5,
                'execution_id': config['EXECUTION_ID_TEST'],
                'max': 547329.0,
                'min': 533106.0,
                'node': 'test1'
            },
            {
                'average': 534814.0,
                'execution_id': config['EXECUTION_ID_TEST'],
                'max': 540183.0,
                'min': 529445.0,
                'node': 'test2'
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

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_many([
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


def test_node_statistics_pagination(client, mongo, config):
    def make_node_reg(node_id, started_at, finished_at):
        return {
            'started_at': started_at,
            'finished_at': finished_at,
            'execution': {
                'id': config['EXECUTION_ID_TEST'],
            },
            'node': {
                'id': node_id,
            },
        }

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_many([
        make_node_reg('test1', make_date(), make_date(2018, 5, 10, 4, 5, 6)),
        make_node_reg('test2', make_date(), make_date(2018, 5, 10, 6, 3, 3)),
        make_node_reg('test1', make_date(), make_date(2018, 5, 10, 8, 2, 9)),
        make_node_reg('test2', make_date(), make_date(2018, 5, 10, 3, 4, 5)),
        make_node_reg('test2', make_date(), None),
    ])

    res = client.get('/v1/process/{}/statistics?offset=1&limit=2'.format(
        config['EXECUTION_ID_TEST']
    ))
    assert res.status_code == 200
    assert len(json.loads(res.data)['data']) == 2


def test_process_statistics_pagination(client, mongo, config):
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

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_many([
        make_exec_reg('p1', make_date(), make_date(2018, 5, 10, 4, 5, 6)),
        make_exec_reg('p2', make_date(), make_date(2018, 5, 10, 10, 34, 32)),
        make_exec_reg('p1', make_date(), make_date(2018, 5, 11, 22, 41, 10)),
        make_exec_reg('p2', make_date(), make_date(2018, 6, 23, 8, 15, 1)),
    ])

    res = client.get('/v1/process/statistics?offset=1&limit=1')

    assert res.status_code == 200
    assert len(json.loads(res.data)['data']) == 1
