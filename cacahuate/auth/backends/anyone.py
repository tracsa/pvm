''' NOT FOR USE IN PRODUCTION '''
from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthenticationError
from cacahuate.http.wsgi import app
from cacahuate.models import User


class AnyoneAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or \
           'password' not in credentials:
            raise AuthenticationError

        # Use credentials to authenticate
        identifier = credentials['username']
        password = credentials['password']

        # fetchs redis mirror user if there is None then creates one
        user = User.get_by('identifier', identifier)

        if user is None:
            user = User(
                identifier=identifier,
                email=identifier + '@mailinator.com',
                fullname=identifier,
            ).save()

        return user
