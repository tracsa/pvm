from flask import request, jsonify

from wsgi import app
from pvm.forms import ContinueProcess

@app.route('/')
def index():
    return jsonify({
        'hello': 'world',
    })

@app.route('/v1/pointer', methods=['POST'])
def continue_process():
    data = ContinueProcess.validate(**request.form.to_dict())

# TODO validate specific data required for the node to continue
# TODO trigger continue process

    return jsonify({
        'data': {
            'detail': 'accepted',
        },
    }), 202
