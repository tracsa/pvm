from coralillo.errors import ValidationErrors, ModelNotFoundError, BadField
from flask import jsonify

from pvm.http.wsgi import app
from pvm.http.errors import NeedsJson

@app.errorhandler(ValidationErrors)
def handle_validation_errors(e):
    return jsonify({'errors': e.to_json()}), 400

@app.errorhandler(NeedsJson)
def handle_bad_request(e):
    return jsonify({
        'errors': [{
            'detail': 'request body must be json',
            'where': 'request.body',
        }],
    }), 400
