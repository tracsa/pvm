from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthenticationError
from cacahuate.models import User


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials:
            raise AuthenticationError('request.body.username.required')
        if 'password' not in credentials:
            raise AuthenticationError('request.body.password.required')

        username = credentials['username']
        password = credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthenticationError('request.body.username.invalid')

        user = User.get_by('identifier', username)

        if user is None:
            user = User(
                identifier=username,
                fullname='Juan Peréz',
                email='hardcoded@mailinator.com'
            ).save()

        return user
