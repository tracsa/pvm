from flask import request, jsonify
import json
import pika

from pvm.wsgi import app
from pvm.forms import ContinueProcess
from pvm.rabbit import get_channel

@app.route('/')
def index():
    return jsonify({
        'hello': 'world',
    })

@app.route('/v1/pointer', methods=['POST'])
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
