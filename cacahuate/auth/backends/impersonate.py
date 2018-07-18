from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthFieldRequired, AuthFieldInvalid
from cacahuate.models import User
from passlib.hash import pbkdf2_sha256


class ImpersonateAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials:
            raise AuthFieldRequired('username')
        if 'password' not in credentials:
            raise AuthFieldRequired('password')

        # fetchs redis mirror user if there is None then creates one
        user = User.get_by('identifier', credentials['username'])

        if not user:
            raise AuthFieldInvalid('username')

        verified = pbkdf2_sha256.verify(
            credentials['password'],
            self.config['IMPERSONATE_PASSWORD'],
        )

        if not verified:
            raise AuthFieldInvalid('password')

        return user.identifier, user.to_json()
