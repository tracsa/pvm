from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthenticationError
from cacahuate.models import User


class HardcodedAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials:
            raise AuthenticationError({
                'detail': 'username is required',
                'code': 'validation.required',
                'where': 'request.body.username',
            })
        if 'password' not in credentials:
            raise AuthenticationError({
                'detail': 'password is required',
                'code': 'validation.required',
                'where': 'request.body.password',
            })

        username = credentials['username']
        password = credentials['password']

        if username != 'juan' or password != '123456':
            raise AuthenticationError({
                'detail': 'Invalid username',
                'code': 'validation.invalid',
                'where': 'request.body.username',
            })

        user = User.get_by('identifier', username)

        if user is None:
            user = User(
                identifier=username,
                fullname='Juan Peréz',
                email='hardcoded@mailinator.com'
            ).save()

        return user
