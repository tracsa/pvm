from flask import jsonify, request
from functools import wraps
from werkzeug.exceptions import BadRequest as WBadRequest
from flask import g
from cacahuate.http.errors import BadRequest, Unauthorized
from cacahuate.models import User, Token
from cacahuate.http.wsgi import app


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

        res = view(*args, **kwargs)

        if type(res) == tuple:
            return tuple([jsonify(res[0])] + list(res[1:]))
        else:
            return jsonify(res)
    return wrapper


def requires_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.authorization is None:
            raise Unauthorized([{
                'detail': 'You must provide basic authorization headers',
                'where': 'request.authorization',
            }])

        identifier = request.authorization['username']
        token = request.authorization['password']

        user = User.get_by('identifier', identifier)
        token = Token.get_by('token', token)

        if (
            user is None or token is None or
            token.proxy.user.get().id != user.id
        ):
            raise Unauthorized([{
                'detail': 'Your credentials are invalid, sorry',
                'where': 'request.authorization',
            }])

        g.user = user

        return view(*args, **kwargs)
    return wrapper


def pagination(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        limit = request.args.get(
            'limit', app.config['PAGINATION_LIMIT']
        )
        offset = request.args.get(
            'offset', app.config['PAGINATION_OFFSET']
        )

        if not type(limit) == int and not limit.isdigit():
            limit = app.config['PAGINATION_LIMIT']

        if not type(offset) == int and not offset.isdigit():
            offset = app.config['PAGINATION_OFFSET']

        g.offset = int(offset)
        g.limit = int(limit)

        return view(*args, **kwargs)
    return wrapper
