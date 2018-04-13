from cacahuate.auth.base import BaseAuthProvider, BaseUser
from cacahuate.errors import AuthenticationError


class HardcodedUser(BaseUser):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_identifier(self):
        return self.username

    def get_x_info(self, medium):
        return "hardcoded@mailinator.com"


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
