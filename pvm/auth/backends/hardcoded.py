from .base import BaseAuthProvider
from pvm.errors import AuthenticationError


class HardcodedAuthProvider(BaseAuthProvider):

    def check_credentials(self):
        if 'username' not in self.credentials or \
           'password' not in self.credentials:
            raise AuthenticationError

        username = self.credentials['username']
        password = self.credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthenticationError
