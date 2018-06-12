from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthFieldRequired, AuthFieldInvalid


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials:
            raise AuthFieldRequired('username')
        if 'password' not in credentials:
            raise AuthFieldRequired('password')

        username = credentials['username']
        password = credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthFieldInvalid('password')

        return username, {
            'identifier': username,
            'fullname': 'Juan Peréz',
            'email': 'hardcoded@mailinator.com'
        }
