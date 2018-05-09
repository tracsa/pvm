from coralillo.errors import ValidationErrors, ModelNotFoundError, BadField
from flask import jsonify

from cacahuate.http.wsgi import app
from cacahuate.http.errors import JsonReportedException
from cacahuate.errors import InputError


@app.errorhandler(JsonReportedException)
def json_formatted_handler(e):
    return jsonify(e.to_json()), e.status_code, e.headers


@app.errorhandler(ModelNotFoundError)
def handle_model_not_found(e):
    return jsonify({
        'errors': [{
            'detail': str(e),
            'where': 'request.url',
        }],
    }), 404


@app.errorhandler(InputError)
def handle_input_error(e):
    return jsonify({
        'errors': [e.to_json()],
    }), 400


@app.errorhandler(404)
def handle_404(e):
    return jsonify({
        'errors': [{
            'detail': e.description,
            'where': 'request.url',
        }],
    }), e.code


@app.errorhandler(405)
def handle_405(e):
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
            'detail': str(e),
            'where': 'request.body',
        }],
    }), e.code


@app.errorhandler(500)
def handle_500(e):
    return jsonify({
        'errors': [{
            'detail': str(e),
            'where': 'server',
        }],
    }), 500
