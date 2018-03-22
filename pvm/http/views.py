from flask import request, jsonify, json
import pika

from pvm.http.wsgi import app
from pvm.http.forms import ContinueProcess
from pvm.http.middleware import requires_json
from pvm.http.errors import MissingField
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
        raise MissingField('process_name')

    xml = Xml.load(app.config, request.json['process_name'])

    start_point = xml.find(lambda e:'class' in e.attrib and e.attrib['class'] == 'start')

    execution = Execution(
        process_name = xml.name,
    ).save()

    pointer = Pointer(
        node_id = start_point.attrib.get('id'),
    ).save()

    pointer.proxy.execution.set(execution)

    return {
        'data': {
            'detail': 'accepted',
        },
    }

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
