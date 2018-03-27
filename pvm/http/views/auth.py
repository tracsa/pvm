from flask import request, jsonify, abort
from pvm.http.wsgi import app
from pvm.errors import AuthenticationError
from datetime import datetime

@app.route('/v1/auth/signin/<AuthProvider:backend>', methods=['POST'])
def signin(backend):
    try:
        user_data = backend.authenticate(
            username=request.form.get('username'),
            password=request.form.get('password'),
        )
    except AuthenticationError:
        abort(401, 'Provided user credentials are invalid')

    return jsonify({
        'data': {
            'token': 'de',
            'expires_at': datetime.now().isoformat(),
        },
    })
