from flask import request

from pvm_api import app
from lib.forms import ContinueProcess

@app.route('/')
def index():
    return jsonify({
        'hello': 'world',
    })

@app.route('/v1/pointer', methods=['POST'])
def continue_process():
    data = ContinueProcess.validate(**request.form)

    return jsonify({
        'data': {},
    })
