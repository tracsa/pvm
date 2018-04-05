from coralillo.errors import ModelNotFoundError
from datetime import datetime
from flask import g
from flask import request, jsonify, json
import os
import pika

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
from cacahuate.xml import Xml, form_to_dict


def trans_id(obj):
    obj['_id'] = str(obj['_id'])
    return obj


def trans_date(obj):
    obj['started_at'] = \
        obj['started_at'].isoformat() if (
                                        obj['started_at'] is not None
                                        ) else None
    obj['finished_at'] = \
        obj['finished_at'].isoformat() if (
                                        obj['finished_at'] is not None
                                        ) else None
    return obj


@app.route('/', methods=['GET', 'POST'])
@requires_json
def index():
    if request.method == 'GET':
        return {
            'hello': 'world',
        }
    elif request.method == 'POST':
        return request.json


@app.route('/v1/execution', methods=['POST'])
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
            'detail': '{} process lacks important nodes and structure'
                      .format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    try:
        start_point = xml.start_node()
    except ElementNotFound as e:
        raise UnprocessableEntity([{
            'detail': '{} process does not have a start node, thus cannot be '
                      'started'.format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    # Check for authorization
    auth_ref, user = validate_auth(start_point)

    # check if there are any forms present
    collected_forms = validate_forms(start_point)

    # save the data
    execution = Execution(
        process_name=xml.filename,
    ).save()

    pointer = Pointer(
        node_id=start_point.getAttribute('id'),
    ).save()

    pointer.proxy.execution.set(execution)

    actors = []
    if auth_ref is not None:
        activity = Activity(ref=auth_ref).save()
        activity.proxy.user.set(user)
        activity.proxy.execution.set(execution)
        actors.append({'ref': auth_ref, 'user': user.to_json()})
    forms = []

    if len(collected_forms) > 0:
        for ref, form_data in collected_forms:
            ques = Questionaire(ref=ref, data=form_data).save()
            ques.proxy.execution.set(execution)
            forms.append({'ref': ref, 'data': form_data})

    # log to mongo
    collection = mongo.db[app.config['MONGO_HISTORY_COLLECTION']]

    collection.insert_one({
        'started_at': datetime.now(),
        'finished_at': datetime.now(),
        'execution_id': execution.id,
        'node_id': start_point.getAttribute('id'),
        'forms': forms,
        'actors': actors,
        'documents': []
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
    auth_ref, user = validate_auth(continue_point, execution)

    # Validate asociated forms
    collected_forms = validate_forms(continue_point)

    # save the data
    actors = []

    if auth_ref is not None:
        activity = Activity(ref=auth_ref).save()
        activity.proxy.user.set(user)
        activity.proxy.execution.set(execution)

        actors.append({'ref': auth_ref, 'user': user.to_json()})

    forms = []
    if len(collected_forms) > 0:
        for ref, form_data in collected_forms:
            ques = Questionaire(ref=ref, data=form_data).save()
            ques.proxy.execution.set(execution)
            forms.append({'ref': ref, 'data': form_data})

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange='',
        routing_key=app.config['RABBIT_QUEUE'],
        body=json.dumps({
            'command': 'step',
            'process': execution.process_name,
            'pointer_id': pointer.id,
            'forms': forms,
            'actors':  actors,
            'documents': []
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
        try:
            start_node = xml.start_node()
        except ElementNotFound:
            return None

        json_xml = xml.to_json()
        forms = []

        for form in start_node.getElementsByTagName('form'):
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

    return jsonify({
        'data': list(map(
            lambda a: a.to_json(embed=['execution']),
            activities
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
        'data': activity.to_json(),
    })


@app.route('/v1/log/<id>', methods=['GET'])
def list_logs(id):
    collection = mongo.db[app.config['MONGO_HISTORY_COLLECTION']]
    node_id = request.args.get('node_id')
    query = {'execution_id': id}
    if node_id:
        query['node_id'] = node_id
    return jsonify({
        "data": list(map(
            trans_date,
            map(
                trans_id,
                collection.find(query)
            )
        )),
    }), 200
