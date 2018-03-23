from flask import request, jsonify, json
import pika

from pvm.http.wsgi import app
from pvm.http.forms import ContinueProcess
from pvm.http.middleware import requires_json
from pvm.http.errors import BadRequest, NotFound, UnprocessableEntity, Unauthorized
from pvm.errors import ProcessNotFound, ElementNotFound
from pvm.models import Execution, Pointer
from pvm.rabbit import get_channel
from pvm.xml import Xml

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
    if 'process_name' not in request.json:
        raise BadRequest([{
            'detail': 'process_name is required',
            'where': 'request.body.process_name',
        }])

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

    # Validate authentication
    auth = start_point.getElementsByTagName('auth')

    if len(auth) > 0:
        # Validate provided authentication againts auth backend
        if request.authorization is None:
            raise Unauthorized([{
                'detail': 'You must provide basic authorization headers',
                'where': 'request.authorization',
            }])

    execution = Execution(
        process_name = xml.name,
    ).save()

    pointer = Pointer(
        node_id = start_point.getAttribute('id'),
    ).save()

    pointer.proxy.execution.set(execution)

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
    data = ContinueProcess.validate(**request.form.to_dict())

# TODO validate specific data required for the node to continue
    channel = get_channel()
    channel.basic_publish(
        exchange = '',
        routing_key = app.config['RABBIT_QUEUE'],
        body = json.dumps({
            'command': 'step',
            'process': data.execution.process_name,
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
        ),
    )

    return {
        'data': {
            'detail': 'accepted',
        },
    }, 202
