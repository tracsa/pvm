from cacahuate.auth.base import BaseAuthProvider
from cacahuate.utils import clear_email
from cacahuate.errors import AuthFieldRequired


class AnyoneAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or not credentials['username'] or \
                not credentials['username'].strip():
            raise AuthFieldRequired('username')

        email = credentials['username'].strip()
        username = clear_email(email)

        return (username, {
            'identifier': username,
            'email': email,
            'fullname': email,
        })
