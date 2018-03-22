from flask import jsonify, request
from functools import wraps
from werkzeug.exceptions import BadRequest

from pvm.http.errors import NeedsJson

def requires_json(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == 'POST':
            if request.headers.get('Content-Type') != 'application/json':
                raise NeedsJson

            try:
                request.get_json()
            except BadRequest:
                raise NeedsJson
        return jsonify(view(*args, **kwargs))
    return wrapper
