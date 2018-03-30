from .base import BaseAuthProvider
from pvm.errors import AuthenticationError


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or \
           'password' not in credentials:
            raise AuthenticationError

        username = credentials['username']
        password = credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthenticationError

        return {
            'identifier': 'harcoded/' + username,
        }
