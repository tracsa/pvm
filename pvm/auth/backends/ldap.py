from ldap3 import Server, Connection, ALL, NTLM, core
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError

from cacahuate.auth.base import BaseAuthProvider, BaseUser
from cacahuate.errors import AuthenticationError
from cacahuate.http.wsgi import app


class LdapUser(BaseUser):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_identifier(self):
        return self.username


class LdapAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or \
           'password' not in credentials:
            raise AuthenticationError

        domain = app.config['LDAP_DOMAIN']
        if 'domain' in credentials:
            domain = credentials['domain']

        username = '{domain}\\{username}'.format(
            domain=domain,
            username=credentials['username'],
        )

        password = credentials['password']

        server = Server(
            app.config['LDAP_URI'],
            get_info=ALL,
            use_ssl=app.config['LDAP_SSL'],
        )

        try:
            conn = Connection(
                server,
                user=username,
                password=password,
                auto_bind=True,
                authentication=NTLM,
            )
        except LDAPBindError:
            raise AuthenticationError

        return LdapUser(
            username=username
        )
