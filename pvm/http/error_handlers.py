from coralillo.errors import ValidationErrors, ModelNotFoundError, BadField
from flask import jsonify

from pvm.http.wsgi import app
from pvm.http.errors import JsonReportedException

@app.errorhandler(JsonReportedException)
def json_formatted_handler(e):
    return jsonify(e.to_json()), e.status_code
