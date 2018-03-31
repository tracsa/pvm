from coralillo.errors import ModelNotFoundError
from flask import request, jsonify, json
import pika
import os

from pvm.http.wsgi import app
from pvm.http.forms import ContinueProcess
from pvm.http.middleware import requires_json
from pvm.http.errors import BadRequest, NotFound, UnprocessableEntity
from pvm.errors import ProcessNotFound, ElementNotFound, ValidationErrors
from pvm.models import Execution, Pointer, User, Token, Activity, Questionaire
from pvm.rabbit import get_channel
from pvm.xml import Xml, get_ref, form_to_dict
from pvm.validation import validate_forms, validate_json, validate_auth

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
            'detail': '{} process does not exist'.format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    try:
        start_point = xml.find(lambda e:e.getAttribute('class') == 'start')
    except ElementNotFound as e:
        raise UnprocessableEntity([{
            'detail': '{} process does not have a start node, thus cannot be started'.format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    # Check for authorization
    auth_ref, user = validate_auth(start_point, request)

    # check if there are any forms present
    collected_forms = validate_forms(start_point, request)

    # save the data
    execution = Execution(
        process_name = xml.name,
    ).save()

    pointer = Pointer(
        node_id = start_point.getAttribute('id'),
    ).save()

    pointer.proxy.execution.set(execution)

    if auth_ref is not None:
        activity = Activity(ref=auth_ref).save()
        activity.proxy.user.set(user)
        activity.proxy.execution.set(execution)

    if len(collected_forms) > 0:
        for ref, form_data in collected_forms:
            ques = Questionaire(ref=ref, data=form_data).save()
            ques.proxy.execution.set(execution)

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange = '',
        routing_key = app.config['RABBIT_QUEUE'],
        body = json.dumps({
            'command': 'step',
            'process': execution.process_name,
            'pointer_id': pointer.id,
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
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
        continue_point = xml.find(lambda e:e.getAttribute('id') == node_id)
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
    auth_ref, user = validate_auth(continue_point, request)

    # Validate asociated forms
    collected_forms = validate_forms(continue_point, request)

    # save the data
    if auth_ref is not None:
        activity = Activity(ref=auth_ref).save()
        activity.proxy.user.set(user)
        activity.proxy.execution.set(execution)

    if len(collected_forms) > 0:
        for ref, form_data in collected_forms:
            ques = Questionaire(ref=ref, data=form_data).save()
            ques.proxy.execution.set(execution)

    # trigger rabbit
    channel = get_channel()
    channel.basic_publish(
        exchange = '',
        routing_key = app.config['RABBIT_QUEUE'],
        body = json.dumps({
            'command': 'step',
            'process': execution.process_name,
            'pointer_id': pointer.id,
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
        ),
    )

    return {
        'data': 'accepted',
    }, 202

@app.route('/v1/process', methods=['GET'])
def list_process():
    # Get all processes
    files = reversed(sorted(os.listdir(app.config['XML_PATH'])))

    # Load only the oldest processes
    processes = {}
    for filename in files:
        process_name = filename.split('.')[0]
        if not process_name in processes:
            processes[process_name] = {
                'name': process_name,
                'xml': Xml(app.config, filename),
            }

    # Get first nodes
    def get_start_point(xml):
        try:
            start_point = xml.find(lambda e:e.getAttribute('class') == 'start')
        except ElementNotFound:
            start_point = None

        return start_point

    processes = list(filter(
        lambda p:p['start_node'] != None,
        map(
            lambda p:{
                'name': p['name'],
                'xml': p['xml'],
                'start_node': get_start_point(p['xml']),
            },
            processes.values()
        )
    ))

    for process in processes:
        process['form'] = list(map(
            form_to_dict,
            process['start_node'].getElementsByTagName('form'),
        ))

        process['name'] = 'test'
        process['description'] = 'test'

        del process['xml']
        del process['start_node']

    print(json.dumps(processes, indent=4))

    return jsonify(processes)

@app.route('/v1/activity', methods=['GET'])
def list_activities():
    pass
