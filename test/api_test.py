from datetime import datetime
from flask import json, jsonify
import pika
import pytest
from cacahuate.handler import Handler
from cacahuate.models import Pointer, Execution, Activity, Questionaire

from .utils import make_auth, make_activity, make_pointer, make_user


def test_continue_process_asks_for_user(client, models):
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


def test_continue_process_requires_valid_node(client, models):
    user = make_user('juan', 'Juan')
    exc = Execution(
        process_name='decision.2018-02-27',
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


def test_continue_process_requires_living_pointer(client, models):
    user = make_user('juan', 'Juan')
    exc = Execution(
        process_name='decision.2018-02-27',
    ).save()

    res = client.post('/v1/pointer', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'execution_id': exc.id,
        'node_id': '57TJ0V3nur6m7wvv',
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


def test_continue_process_requires_user_hierarchy(client, models):
    ''' a node whose auth has a filter must be completed by a person matching
    the filter '''
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'manager')

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

    assert False, 'users with a task can resolve, users without it cannot'


def test_continue_process_requires_data(client, models):
    juan = make_user('juan', 'Juan')
    act = Activity(ref='requester').save()
    act.proxy.user.set(juan)

    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'manager')
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
            'detail': "form count lower than expected for ref auth-form",
            'where': 'request.body.form_array',
        }],
    }


def test_continue_process(client, models, mocker, config):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')
    manager = make_user('juan_manager', 'Juanote')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'manager')
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
                'ref': 'auth-form',
                'data': {
                    'auth': 'yes',
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

    activity = next(exc.proxy.actors.q().filter(ref='manager'))

    assert activity.ref == 'manager'
    assert activity.proxy.user.get() == manager

    # form is attached
    forms = exc.proxy.forms.get()

    assert len(forms) == 1

    form = forms[0]

    assert form.ref == 'auth-form'
    assert form.data == {
        'auth': 'yes',
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
            'ref': 'manager',
            'user': {
                'identifier': 'juan_manager',
                'human_name': 'Juanote',
            },
            'forms': [
                {
                    'ref': 'auth-form',
                    'form': [
                        {
                            "name": "auth",
                            "options": [
                                {
                                    "label": "\u00c1ndale mijito, ve",
                                    "value": "yes"
                                },
                                {
                                    "label": "Ni madres",
                                    "value": "no"
                                }
                            ],
                            "type": "radio",
                            "value": "yes",
                            'label': None,
                        }
                    ],
                    'data': {
                        'auth': 'yes',
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


def test_start_process_simple_requires(client, models, mongo, config):
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

    # we need a process able to load
    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'nostart',
    }))

    assert res.status_code == 422
    assert json.loads(res.data) == {
        'errors': [
            {
                'detail': 'Process does not have the start node',
                'where': 'request.body.process_name',
            },
        ],
    }

    # no registry should be created yet
    assert mongo[config["MONGO_HISTORY_COLLECTION"]].count() == 0
    assert Activity.count() == 0
    assert Questionaire.count() == 0


def test_start_process_simple(client, models, mocker, config, mongo):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
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
        'forms': [],
        'actors': [{
            'ref': 'start-node',
            'user_id': juan.id,
        }],
    }

    reg2 = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg2['id'] == exc.id
    assert reg2['status'] == 'ongoing'


def test_exit_request_requirements(client, models):
    # first requirement is to have authentication
    res = client.post('/v1/execution', headers={
        'Content-Type': 'application/json',
    }, data=json.dumps({
        'process_name': 'exit_request',
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
        'process_name': 'exit_request',
    }))

    assert res.status_code == 400
    assert json.loads(res.data) == {
        'errors': [{
            'detail': "form count lower than expected for ref exit-form",
            'where': 'request.body.form_array',
        }],
    }

    assert Execution.count() == 0
    assert Activity.count() == 0


def test_exit_request_start(client, models, mocker, mongo, config):
    user = make_user('juan', 'Juan')

    assert Execution.count() == 0
    assert Activity.count() == 0

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(user)}, data=json.dumps({
        'process_name': 'exit_request',
        'form_array': [
            {
                'ref': 'exit-form',
                'data': {
                    'reason': 'tenía que salir al baño',
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

    assert activity.ref == 'requester'
    assert activity.proxy.user.get() == user

    # form is attached
    forms = exc.proxy.forms.get()

    assert len(forms) == 1

    form = forms[0]

    assert form.ref == 'exit-form'
    assert form.data == {
        'reason': 'tenía que salir al baño',
    }

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['state'] == {
        'forms': [{
            'ref': 'exit-form',
            'data': {
                'reason': 'tenía que salir al baño',
            },
        }],
        'actors': [
            {
                'ref': 'requester',
                'user_id': user.id,
            }
        ],
    }


def test_list_processes(client):
    res = client.get('/v1/process')

    body = json.loads(res.data)
    exit_req = list(filter(
        lambda xml: xml['id'] == 'exit_request', body['data']
    ))[0]

    assert res.status_code == 200
    assert exit_req == {
        'id': 'exit_request',
        'version': '2018-03-20',
        'author': 'categulario',
        'date': '2018-03-20',
        'name': 'Petición de salida',
        'description':
            'Este proceso es iniciado por un empleado que quiere salir'
            ' temporalmente de la empresa (e.g. a comer). La autorización'
            ' llega a su supervisor, quien autoriza o rechaza la salida, '
            'evento que es notificado de nuevo al empleado y finalmente '
            'a los guardias, uno de los cuales notifica que el empleado '
            'salió de la empresa.',
        'versions': ['2018-03-20'],
        'form_array': [
            {
                'ref': 'exit-form',
                'inputs': [
                    {
                        'type': 'text',
                        'name': 'reason',
                        'required': True,
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


@pytest.mark.skip
def test_read_process(client):
    res = client.get('/v1/process/exit_request')

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': {
            'name': 'exit_request.2018-03-20',
        },
    }

    res = client.get('/v1/process/oldest?v=2018-02-14')

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': {
            'name': 'exit_request.2018-03-20',
        },
    }


def test_list_activities_requires(client):
    res = client.get('/v1/activity')
    assert res.status_code == 401


def test_list_activities(client, models):
    '''Given 4 activities, two for the current user and two for
    another, list only the two belonging to him or her'''
    juan = make_user('juan', 'Juan')
    other = make_user('other', 'Otero')

    exc = Execution(
        process_name='exit_request.2018-03-20.xml',
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


def test_activity_wrong_activity(client, models):
    # validate user authentication correct but bad activity
    juan = make_user('juan', 'Juan')
    other = make_user('other', 'Otero')

    exc = Execution(
        process_name='exit_request.2018-03-20.xml',
    ).save()

    act = make_activity('requester', juan, exc)
    act2 = make_activity('some', other, exc)

    res = client.get(
        '/v1/activity/{}'.format(act2.id),
        headers=make_auth(juan)
    )

    assert res.status_code == 403


def test_activity(client, models):
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
            'id': "15asbs",
        },
        'node': {
            'id': 'mid-node',
        },
    })

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 50),
        'finished_at': None,
        'execution': {
            'id': "15asbs",
        },
        'node': {
            'id': '4g9lOdPKmRUf2',
        },
    })

    res = client.get('/v1/log/15asbs?node_id=mid-node')

    ans = json.loads(res.data)
    del ans['data'][0]['_id']

    assert res.status_code == 200
    assert ans == {
        "data": [{
            'started_at': '2018-04-01T21:45:00+00:00',
            'finished_at': None,
            'execution': {
                'id': '15asbs',
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


def test_task_list(client, models):
    juan = make_user('user', 'User')

    pointer = make_pointer('exit_request.2018-03-20.xml', 'manager')
    juan.proxy.tasks.set([pointer])

    res = client.get('/v1/task', headers=make_auth(juan))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': [pointer.to_json(embed=['execution'])],
    }


def test_task_read_requires_auth(client, models):
    res = client.get('/v1/task/foo')

    assert res.status_code == 401


def test_task_read_requires_real_pointer(client, models):
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/foo', headers=make_auth(juan))

    assert res.status_code == 404


def test_task_read_requires_assigned_task(client, models):
    ptr = make_pointer('dumb.2018-04-06.xml', 'node2')
    juan = make_user('juan', 'Juan')

    res = client.get('/v1/task/{}'.format(ptr.id), headers=make_auth(juan))

    assert res.status_code == 403


def test_task_read(client, models):
    ptr = make_pointer('dumb.2018-04-06.xml', 'node2')
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
                    'ref': 'formulario2',
                    'inputs': [
                        {
                            'label': '¿Asignarme más chamba?',
                            'name': 'continue',
                            'required': True,
                            'type': 'select',
                            'options': [
                                {
                                    'label': 'Simona la changa',
                                    'value': 'yes',
                                },
                                {
                                    'label': 'Nel pastel',
                                    'value': 'no',
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    }


def test_execution_has_node_info(client, models):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'dumb',
        'form_array': [
            {
                'ref': 'formulario',
                'data': {
                    'continue': 'yes',
                },
            },
        ],
    }))

    assert res.status_code == 201

    exe = Execution.get_all()[0]
    ptr = Pointer.get_all()[0]

    assert exe.name == 'Proceso simple'
    assert exe.description == 'Te asigna una tarea a ti mismo'

    assert ptr.name == 'Primer paso ;)'
    assert ptr.description == 'Te asignas chamba'


def test_log_has_node_info(client, models):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'dumb',
        'form_array': [
            {
                'ref': 'formulario',
                'data': {
                    'continue': 'yes',
                },
            },
        ],
    }))
    body = json.loads(res.data)
    execution_id = body['data']['id']

    res = client.get('/v1/log/{}'.format(execution_id))
    body = json.loads(res.data)
    data = body['data'][0]

    assert data['node']['id'] == 'requester'
    assert data['node']['name'] == 'Primer paso ;)'
    assert data['node']['description'] == 'Te asignas chamba'

    assert data['execution']['id'] == execution_id
    assert data['execution']['name'] == 'Proceso simple'
    assert data['execution']['description'] == 'Te asigna una tarea a ti mismo'


def test_log_has_form_input_data(client, models):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'dumb',
        'form_array': [
            {
                'ref': 'formulario',
                'data': {
                    'continue': 'yes',
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
            "label": "\u00bfAsignarme la chamba?",
            "name": "continue",
            "options": [
                {
                    "label": "Simona la changa",
                    "value": "yes"
                },
                {
                    "label": "Nel pastel",
                    "value": "no"
                }
            ],
            "type": "select",
            "value": "yes"
        }
    ]


def test_delete_process(config, client, mongo, mocker):
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    p_0 = make_pointer('exit_request.2018-03-20.xml', 'manager')
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


def test_status_notfound(client, models):
    res = client.get('/v1/execution/doo')

    assert res.status_code == 404


def test_status(config, client, models, mongo):
    ptr = make_pointer('exit_request.2018-03-20.xml', 'manager')
    execution = ptr.proxy.execution.get()

    oid = mongo[config['MONGO_EXECUTION_COLLECTION']].insert_one({
        'id': execution.id,
    })

    res = client.get('/v1/execution/{}'.format(execution.id))

    assert res.status_code == 200
    assert json.loads(res.data) == {
        'data': {
            '_id': str(oid.inserted_id),
            'id': execution.id,
        },
    }
