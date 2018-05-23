from coralillo.errors import ModelNotFoundError
from datetime import datetime
from flask import g, abort
from flask import request, jsonify, json
from functools import reduce
import os
import pika
import pymongo

from cacahuate.errors import ProcessNotFound, ElementNotFound, MalformedProcess
from cacahuate.http.errors import BadRequest, NotFound, UnprocessableEntity, \
    Forbidden
from cacahuate.http.middleware import requires_json, requires_auth, \
    pagination
from cacahuate.http.validation import validate_json, validate_auth
from cacahuate.http.wsgi import app, mongo
from cacahuate.models import Execution, Pointer, User, Token
from cacahuate.rabbit import get_channel
from cacahuate.xml import Xml, form_to_dict, get_text
from cacahuate.node import make_node


DATE_FIELDS = [
    'started_at',
    'finished_at',
]


def json_prepare(obj):
    if obj.get('_id'):
        del obj['_id']

    for field in DATE_FIELDS:
        if obj.get(field) and type(obj[field]) == datetime:
            obj[field] = obj[field].isoformat()

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


@app.route('/v1/execution', methods=['GET'])
@pagination
def execution_list():
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]

    return jsonify({
        "data": list(map(
            json_prepare,
            collection.find().skip(g.offset).limit(g.limit)
        )),
    })


@app.route('/v1/execution/<id>', methods=['GET'])
def process_status(id):
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]

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

    xmliter = iter(xml)
    node = make_node(next(xmliter), xmliter)

    # Check for authorization
    validate_auth(node, g.user)

    # check if there are any forms present
    input = node.validate_input(request.json)

    # get rabbit channel for process queue
    channel = get_channel()

    execution = xml.start(node, input, mongo.db, channel, g.user.identifier)

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

    xml = Xml.load(app.config, execution.process_name, direct=True)
    xmliter = iter(xml)

    try:
        continue_point = make_node(
            xmliter.find(lambda e: e.getAttribute('id') == node_id),
            xmliter
        )
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
    collected_input = continue_point.validate_input(request.json)

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange='',
        routing_key=app.config['RABBIT_QUEUE'],
        body=json.dumps({
            'command': 'step',
            'pointer_id': pointer.id,
            'user_identifier': g.user.identifier,
            'input': collected_input,
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
        xmliter = iter(xml)
        first_node = next(xmliter)
        xmliter.parser.expandNode(first_node)

        for form in first_node.getElementsByTagName('form'):
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
        )),
    })


@app.route('/v1/process/<name>', methods=['GET'])
def find_process(name):
    version = request.args.get('version', '')

    if version:
        version = ".{}".format(version)

    process_name = "{}{}".format(name, version)

    try:
        xml = Xml.load(app.config, process_name)
    except ProcessNotFound as e:
        raise NotFound([{
            'detail': '{} process does not exist'
                      .format(process_name),
            'where': 'request.body.process_name',
        }])

    return jsonify({
        'data': xml.to_json()
    })


@app.route('/v1/activity', methods=['GET'])
@requires_auth
def list_activities():
    activities = g.user.proxy.activities.get()

    return jsonify({
        'data': list(map(
            lambda a: a.to_json(include=['*', 'execution']),
            activities
        )),
    })


@app.route('/v1/task')
@requires_auth
def task_list():
    return jsonify({
        'data': list(map(
            lambda t: t.to_json(include=['*', 'execution']),
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

    execution = pointer.proxy.execution.get()
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]
    state = collection.find_one({
        'id': execution.id,
    })

    xml = Xml.load(
        app.config,
        execution.process_name,
        direct=True
    )
    xmliter = iter(xml)
    node = xmliter.find(lambda e: e.getAttribute('id') == pointer.node_id)

    xmliter.parser.expandNode(node)

    # Response body
    json_data = pointer.to_json(include=['*', 'execution'])

    # Append node info
    json_data['node_type'] = node.tagName

    # Append forms
    forms = []
    for form in node.getElementsByTagName('form'):
        forms.append(form_to_dict(form))
    json_data['form_array'] = forms

    # If any append previous work done
    node_state = state['state']['items'][pointer.node_id]
    node_actors = node_state['actors']

    user_identifier = g.user.identifier
    if user_identifier in node_actors['items']:
        action = node_actors['items'][user_identifier]

        json_data['prev_work'] = action['forms']

    # Append validation
    if node.tagName == 'validation':
        deps = list(map(
            lambda node: get_text(node),
            node.getElementsByTagName('dep')
        ))

        fields = []
        for dep in deps:
            form_ref, input_name = dep.split('.')

            # TODO this could be done in O(log N + K)
            for node in state['state']['items'].values():
                if node['state'] != 'valid':
                    continue

                for identifier in node['actors']['items']:
                    actor = node['actors']['items'][identifier]
                    if actor['state'] != 'valid':
                        continue

                    for form_ix, form in enumerate(actor['forms']):
                        if form['state'] != 'valid':
                            continue

                        if form['ref'] != form_ref:
                            continue

                        if input_name not in form['inputs']['items']:
                            continue

                        input = form['inputs']['items'][input_name]

                        state_ref = [
                            node['id'],
                            identifier,
                            str(form_ix),
                        ]
                        state_ref = '.'.join(state_ref)
                        state_ref = state_ref + ':' + dep

                        field = {
                            'ref': state_ref,
                            **input,
                        }
                        del field['state']

                        fields.append(field)

        json_data['fields'] = fields

    return jsonify({
        'data': json_data,
    })


@app.route('/v1/log/<id>', methods=['GET'])
@pagination
def list_logs(id):
    collection = mongo.db[app.config['POINTER_COLLECTION']]
    node_id = request.args.get('node_id')
    query = {'execution.id': id}

    if node_id:
        query['node.id'] = node_id

    return jsonify({
        "data": list(map(
            json_prepare,
            collection.find(query).skip(g.offset).limit(g.limit).sort([
                ('started_at', pymongo.DESCENDING)
            ])
        )),
    })


@app.route('/v1/process/<id>/statistics', methods=['GET'])
def node_statistics(id):
    collection = mongo.db[app.config['POINTER_COLLECTION']]
    query = [
        {"$match": {"process_id": id}},
        {"$project": {
            "process_id": "$process_id",
            "node": "$node.id",
            "difference_time": {
                "$subtract": ["$finished_at", "$started_at"],
            },
        }},
        {"$group": {
            "_id": {"process_id": "$process_id", "node": "$node"},
            "process_id": {"$first": "$process_id"},
            "node": {"$first": "$node"},
            "max": {
                "$max": {
                    "$divide": ["$difference_time", 1000],
                },
            },
            "min": {
                "$min": {
                    "$divide": ["$difference_time", 1000],
                },
            },
            "average": {
                "$avg": {
                    "$divide": ["$difference_time", 1000],
                },
            },
        }},

        {"$sort": {"execution": 1, "node": 1}}
    ]
    return jsonify({
        "data": list(map(
            json_prepare,
            collection.aggregate(query)
        )),
    })


@app.route('/v1/process/statistics', methods=['GET'])
@pagination
def process_statistics():
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]
    query = [
        {"$match": {"status": "finished"}},
        {"$skip": g.offset},
        {"$limit": g.limit},
        {"$project": {"difference_time": {
            "$subtract": ["$finished_at", "$started_at"]
            }, "process":{"id": "$process.id"},
        }},

        {"$group": {
            "_id": "$process.id",
            "process": {"$first": "$process.id"},
            "max": {
                "$max": {
                    "$divide": ["$difference_time", 1000],
                },
            },
            "min": {
                "$min": {
                    "$divide": ["$difference_time", 1000],
                },
            },
            "average": {
                "$avg": {
                    "$divide": ["$difference_time", 1000],
                },
            },

        }},
        {"$sort": {"process": 1}},
    ]

    return jsonify({
        "data": list(map(
            json_prepare,
            collection.aggregate(query)
        )),
    })
