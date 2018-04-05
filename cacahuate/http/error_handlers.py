from coralillo.errors import ValidationErrors, ModelNotFoundError, BadField
from flask import jsonify

from cacahuate.http.wsgi import app
from cacahuate.http.errors import JsonReportedException


@app.errorhandler(JsonReportedException)
def json_formatted_handler(e):
    return jsonify(e.to_json()), e.status_code, e.headers


@app.errorhandler(404)
def handle_404(e):
    return jsonify({
        'errors': [{
            'detail': e.description,
            'where': 'request.url',
        }],
    }), e.code


@app.errorhandler(401)
def handle_401(e):
    return jsonify({
        'errors': [{
            'detail': ':'.join(str(e).split(':')[1:])[1:],
            'where': 'request.body',
        }],
    }), e.code


@app.errorhandler(500)
def handle_500(e):
    return jsonify({
        'errors': [{
            'detail': 'The server has failed its mission',
            'where': 'server',
        }],
    })
