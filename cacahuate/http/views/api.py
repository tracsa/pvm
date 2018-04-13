from coralillo.errors import ModelNotFoundError
from datetime import datetime
from flask import g, abort
from flask import request, jsonify, json
from functools import reduce
import os
import pika
import pymongo
from jinja2 import Template

from cacahuate.errors import ProcessNotFound, ElementNotFound, MalformedProcess
from cacahuate.http.errors import BadRequest, NotFound, UnprocessableEntity, \
    Forbidden
from cacahuate.http.forms import ContinueProcess
from cacahuate.http.middleware import requires_json, requires_auth
from cacahuate.http.validation import validate_forms, validate_json, \
    validate_auth
from cacahuate.http.wsgi import app, mongo
from cacahuate.models import Execution, Pointer, User, Token, Activity, \
    Questionaire
from cacahuate.rabbit import get_channel
from cacahuate.xml import Xml, form_to_dict, get_node_info


DATE_FIELDS = [
    'started_at',
    'finished_at',
]


def json_prepare(obj):
    if obj.get('_id'):
        obj['_id'] = str(obj['_id'])

    for field in DATE_FIELDS:
        if obj.get(field) and type(obj[field]) == datetime:
            obj[field] = obj[field].isoformat()

    return obj


def store_forms(collected_forms, execution):
    forms = []

    for ref, form_description in collected_forms:
        form_data = dict(map(
            lambda x: (x['name'], x['value']),
            form_description
        ))

        ques = Questionaire(ref=ref, data=form_data).save()
        ques.proxy.execution.set(execution)
        forms.append({
            'ref': ref,
            'data': form_data,
            'form': form_description,
        })

    return forms


def make_name(name_string, collected_forms):
    context = dict(map(
        lambda i: (i[0], dict(map(
            lambda j: (j['name'], j['value']),
            i[1]
        ))),
        collected_forms
    ))

    return Template(name_string).render(**context)


def store_actor(node, user, execution, forms):
    auth_ref = node.getAttribute('id')
    activity = Activity(ref=auth_ref).save()
    activity.proxy.user.set(g.user)
    activity.proxy.execution.set(execution)

    return {
        'ref': auth_ref,
        'user': {
            'identifier': g.user.identifier,
            'human_name': g.user.human_name,
        },
        'forms': forms,
    }


@app.route('/', methods=['GET', 'POST'])
@requires_json
def index():
    if request.method == 'GET':
        return {
            'hello': 'world',
        }
    elif request.method == 'POST':
        return request.json


@app.route('/v1/execution/<id>', methods=['GET'])
def process_status(id):
    collection = mongo.db[app.config['MONGO_EXECUTION_COLLECTION']]

    try:
        exc = next(collection.find({'id': id}))
    except StopIteration:
        raise ModelNotFoundError(
            'Specified execution never existed, and never will'
        )

    return jsonify({
        'data': json_prepare(exc),
    })


@app.route('/v1/execution/<id>', methods=['DELETE'])
@requires_auth
def delete_process(id):
    execution = Execution.get_or_exception(id)

    channel = get_channel()
    channel.basic_publish(
        exchange='',
        routing_key=app.config['RABBIT_QUEUE'],
        body=json.dumps({
            'command': 'cancel',
            'execution_id': execution.id,
        }),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    return jsonify({
        'data': 'accepted',
    }), 202


@app.route('/v1/execution', methods=['POST'])
@requires_auth
@requires_json
def start_process():
    validate_json(request.json, ['process_name'])

    try:
        xml = Xml.load(app.config, request.json['process_name'])
    except ProcessNotFound as e:
        raise NotFound([{
            'detail': '{} process does not exist'
                      .format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])
    except MalformedProcess as e:
        raise UnprocessableEntity([{
            'detail': str(e),
            'where': 'request.body.process_name',
        }])

    start_point = xml.start_node

    # Check for authorization
    validate_auth(start_point, g.user)

    # check if there are any forms present
    collected_forms = validate_forms(start_point, request.json)

    node_info = get_node_info(start_point)

    # save the data
    execution = Execution(
        process_name=xml.filename,
        name=make_name(xml.name, collected_forms),
        description=xml.description,
    ).save()
    pointer = Pointer(
        node_id=start_point.getAttribute('id'),
        **node_info,
    ).save()
    pointer.proxy.execution.set(execution)

    actor = store_actor(
        start_point,
        g.user,
        execution,
        store_forms(collected_forms, execution)
    )

    # log to mongo
    collection = mongo.db[app.config['MONGO_HISTORY_COLLECTION']]

    collection.insert_one({
        'started_at': datetime.now(),
        'finished_at': datetime.now(),
        'execution': {
            'id': execution.id,
            'name': execution.name,
            'description': execution.description,
        },
        'node': {**{
            'id': start_point.getAttribute('id'),
        }, **node_info},
        'actors': [actor],
        'state': execution.get_state(),
    })

    collection = mongo.db[app.config['MONGO_EXECUTION_COLLECTION']]

    history_execution = collection.insert_one({
        'id': execution.id,
        'name': execution.name,
        'description': execution.description,
        'status': 'ongoing',
        'started_at': datetime.now(),
        'finished_at': None,
    })

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange='',
        routing_key=app.config['RABBIT_QUEUE'],
        body=json.dumps({
            'command': 'step',
            'process': execution.process_name,
            'pointer_id': pointer.id,
        }),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    return {
        'data': execution.to_json(),
    }, 201


@app.route('/v1/pointer', methods=['POST'])
@requires_auth
@requires_json
def continue_process():
    validate_json(request.json, ['execution_id', 'node_id'])

    execution_id = request.json['execution_id']
    node_id = request.json['node_id']

    try:
        execution = Execution.get_or_exception(execution_id)
    except ModelNotFoundError:
        raise BadRequest([{
            'detail': 'execution_id is not valid',
            'code': 'validation.invalid',
            'where': 'request.body.execution_id',
        }])

    xml = Xml.load(app.config, execution.process_name)

    try:
        continue_point = xml.find(lambda e: e.getAttribute('id') == node_id)
    except ElementNotFound as e:
        raise BadRequest([{
            'detail': 'node_id is not a valid node',
            'code': 'validation.invalid_node',
            'where': 'request.body.node_id',
        }])

    try:
        pointer = next(execution.proxy.pointers.q().filter(node_id=node_id))
    except StopIteration:
        raise BadRequest([{
            'detail': 'node_id does not have a live pointer',
            'code': 'validation.no_live_pointer',
            'where': 'request.body.node_id',
        }])

    # Check for authorization
    if pointer not in g.user.proxy.tasks:
        raise Forbidden([{
            'detail': 'Provided user does not have this task assigned',
            'where': 'request.authorization',
        }])

    # Validate asociated forms
    collected_forms = validate_forms(continue_point, request.json)

    # save the data
    actor = store_actor(
        continue_point,
        g.user,
        execution,
        store_forms(collected_forms, execution)
    )

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange='',
        routing_key=app.config['RABBIT_QUEUE'],
        body=json.dumps({
            'command': 'step',
            'pointer_id': pointer.id,
            'actor':  actor,
        }),
        properties=pika.BasicProperties(
            delivery_mode=2,
        ),
    )

    return {
        'data': 'accepted',
    }, 202


@app.route('/v1/process', methods=['GET'])
def list_process():
    def add_form(xml):
        json_xml = xml.to_json()
        forms = []

        for form in xml.start_node.getElementsByTagName('form'):
            forms.append(form_to_dict(form))

        json_xml['form_array'] = forms

        return json_xml

    return jsonify({
        'data': list(filter(
            lambda x: x,
            map(
                add_form,
                Xml.list(app.config),
              )
        ))
    })


@app.route('/v1/activity', methods=['GET'])
@requires_auth
def list_activities():
    activities = g.user.proxy.activities.get()

    seen = {}
    unique = []
    for activity in activities:
        if activity.execution not in seen:
            seen[activity.execution] = True
            unique.append(activity)

    return jsonify({
        'data': list(map(
            lambda a: a.to_json(embed=['execution']),
            unique
        )),
    })


@app.route('/v1/activity/<id>', methods=['GET'])
@requires_auth
def one_activity(id):
    try:
        activity = Activity.get_or_exception(id)
    except ModelNotFoundError:
        raise BadRequest([{
            'detail': 'activity_id is not valid',
            'code': 'validation.invalid',
            'where': 'request.body.execution_id',
        }])

    user_activity = User.get_or_exception(activity.user)
    if not g.user == user_activity:
        raise Forbidden([{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }])

    return jsonify({
        'data': activity.to_json(embed=['execution']),
    })


@app.route('/v1/task')
@requires_auth
def task_list():
    return jsonify({
        'data': list(map(
            lambda t: t.to_json(embed=['execution']),
            g.user.proxy.tasks.get()
        )),
    })


@app.route('/v1/task/<id>', methods=['GET'])
@requires_auth
def task_read(id):
    pointer = Pointer.get_or_exception(id)

    if pointer not in g.user.proxy.tasks:
        raise Forbidden([{
            'detail': 'Provided user does not have this task assigned',
            'where': 'request.authorization',
        }])

    forms = []
    xml = Xml.load(app.config, pointer.proxy.execution.get().process_name)
    node = xml.find(lambda e: e.getAttribute('id') == pointer.node_id)

    for form in node.getElementsByTagName('form'):
        forms.append(form_to_dict(form))

    json_data = pointer.to_json(embed=['execution'])

    json_data['form_array'] = forms

    return jsonify({
        'data': json_data,
    })


@app.route('/v1/log/<id>', methods=['GET'])
def list_logs(id):
    collection = mongo.db[app.config['MONGO_HISTORY_COLLECTION']]
    node_id = request.args.get('node_id')
    query = {'execution.id': id}

    if node_id:
        query['node.id'] = node_id

    return jsonify({
        "data": list(map(
            json_prepare,
            collection.find(query).sort([
                ('started_at', pymongo.DESCENDING)
            ])
        )),
    }), 200
