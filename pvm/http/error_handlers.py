from coralillo.errors import ValidationErrors, ModelNotFoundError, BadField
from flask import jsonify

from pvm.wsgi import app

@app.errorhandler(ValidationErrors)
def handle_validation_errors(e):
    return jsonify({'errors': e.to_json()}), 400
