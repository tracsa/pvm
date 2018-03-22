from flask import jsonify, request
from functools import wraps
from werkzeug.exceptions import BadRequest as WBadRequest

from pvm.http.errors import BadRequest

def requires_json(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == 'POST':
            if request.headers.get('Content-Type') != 'application/json':
                raise BadRequest([{
                    'detail': 'Content-Type must be application/json',
                    'where': 'request.headers.content_type',
                }])

            try:
                request.get_json()
            except WBadRequest:
                raise BadRequest([{
                    'detail': 'request body is not valid json',
                    'where': 'request.body',
                }])
        return jsonify(view(*args, **kwargs))
    return wrapper
