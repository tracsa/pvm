from pvm.auth.base import BaseAuthProvider, BaseUser
from pvm.errors import AuthenticationError


class HardcodedUser(BaseUser):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_identifier(self):
        return self.username


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or \
           'password' not in credentials:
            raise AuthenticationError

        username = credentials['username']
        password = credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthenticationError

        return HardcodedUser(
            username=username,
            password=password,
        )
