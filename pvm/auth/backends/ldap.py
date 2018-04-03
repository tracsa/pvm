from .base import BaseAuthProvider, BaseUser
from ldap3 import Server, Connection, ALL, NTLM, core
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
from pvm.errors import AuthenticationError
from pvm.http.wsgi import app
import sys


class LdapUser(BaseUser):

    def __init__(self, username):
        self.username = username

    def get_username(self, username):
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

        return LdapUser(username)
