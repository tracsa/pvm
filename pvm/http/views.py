from flask import request, jsonify, json
import pika

from pvm.http.wsgi import app
from pvm.http.forms import ContinueProcess
from pvm.http.middleware import requires_json
from pvm.rabbit import get_channel

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
    return jsonify({
        'data': {
            'detail': 'accepted',
        },
    })

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

    return jsonify({
        'data': {
            'detail': 'accepted',
        },
    }), 202
