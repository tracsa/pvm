from flask import request, jsonify, abort
from pvm.http.wsgi import app
from pvm.errors import AuthenticationError
from datetime import datetime

from pvm.http.errors import Unauthorized
from pvm.models import User, Token


@app.route('/v1/auth/signin/<AuthProvider:backend>', methods=['POST'])
def signin(backend):
    try:
        auth = backend.authenticate(request.form.to_dict())
    except AuthenticationError:
        abort(401, 'Provided user credentials are invalid')

    return jsonify(auth)
    '''
        'data': {
            'token': 'de',
            'expires_at': datetime.now().isoformat(),
        },
    })
    '''

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
