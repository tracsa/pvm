from cacahuate.auth.base import BaseAuthProvider


class AnyoneAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        return (credentials['username'], {
            'identifier': credentials['username'],
            'email': credentials['username'],
            'fullname': credentials['username'],
        })
