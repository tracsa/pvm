from coralillo.errors import ModelNotFoundError
from flask import jsonify
import traceback
import logging

from cacahuate.http.wsgi import app
from cacahuate.http.errors import JsonReportedException
from cacahuate.errors import InputError, AuthenticationError

LOGGER = logging.getLogger(__name__)


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


@app.errorhandler(AuthenticationError)
def handler_auth_error(e):
    return jsonify({
        'errors': [e.to_json()],
    }), 401


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
            'code': str(e),
            'where': 'request.authorization',
        }],
    }), e.code


@app.errorhandler(500)
def handle_500(e):
    LOGGER.error(traceback.format_exc())

    return jsonify({
        'errors': [{
            'detail': str(e),
            'where': 'server',
        }],
    }), 500
