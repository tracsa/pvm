from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthFieldRequired


class AnyoneAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or not credentials['username'] or \
                not credentials['username'].strip():
            raise AuthFieldRequired('username')

        email = credentials['username'].strip()

        return (email, {
            'identifier': email,
            'email': email,
            'fullname': email,
        })
