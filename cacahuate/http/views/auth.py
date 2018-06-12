from flask import request, jsonify
from random import choice
from string import ascii_letters

from cacahuate.http.errors import Unauthorized
from cacahuate.http.wsgi import app
from cacahuate.models import User, Token
from cacahuate.utils import get_or_create


@app.route('/v1/auth/signin/<AuthProvider:backend>', methods=['POST'])
def signin(backend):
    # this raises AuthenticationError exception if failed
    identifier, data = backend.authenticate(**request.form.to_dict())

    user = get_or_create(identifier, data)

    # creates auth token
    if user.proxy.tokens.count() > 0:
        token = user.proxy.tokens.get()[0]
    else:
        token = ''.join(choice(ascii_letters) for _ in range(32))
        token = Token(token=token).save()
        token.proxy.user.set(user)

    return jsonify({
        'data': {
            'username': user.identifier,
            'fullname': user.fullname,
            'token': token.token,
        }
    })


@app.route('/v1/auth/whoami')
def whoami():
    identifier = request.authorization['username']
    token = request.authorization['password']

    user = User.get_by('identifier', identifier)
    token = Token.get_by('token', token)

    if user is None or \
       token is None or \
       token.proxy.user.get().id != user.id:
        raise Unauthorized([{
            'detail': 'Your credentials are invalid, sorry',
            'where': 'request.authorization',
        }])

    return jsonify({
        'data': user.to_json(),
    })
