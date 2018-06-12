from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthFieldRequired, AuthFieldInvalid
from cacahuate.models import User


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

        user = User.get_by('identifier', username)

        if user is None:
            user = User(
                identifier=username,
                fullname='Juan Peréz',
                email='hardcoded@mailinator.com'
            ).save()

        return user
