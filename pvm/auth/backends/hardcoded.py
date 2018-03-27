from .base import BaseAuthProvider
from pvm.errors import AuthenticationError


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, username=None, password=None):
        if username == 'juan' and password == '123456':
            return {
                'username': 'juan',
                'password': '123456',
                'email': 'juan@hardcoded.com',
            }

        raise AuthenticationError
