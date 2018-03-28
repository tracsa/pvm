from .base import BaseAuthProvider
from ldap3 import Server, Connection, ALL, NTLM, core
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
from pvm.errors import AuthenticationError
from pvm.http.wsgi import app
import sys


class LdapAuthProvider(BaseAuthProvider):

    @property
    def username(self):
        username = self.credentials['username']

        domain = app.config['LDAP_DOMAIN']
        if 'domain' in self.credentials:
            domain = self.credentials['domain']

        return '{domain}\\{username}'.format(
            domain=domain,
            username=username,
        )

    def check_credentials(self):
        if 'username' not in self.credentials or \
           'password' not in self.credentials:
            raise AuthenticationError

        password = self.credentials['password']

        server = Server(
            app.config['LDAP_URI'],
            get_info=ALL,
            use_ssl=app.config['LDAP_SSL'],
        )

        try:
            conn = Connection(
                server,
                user=self.username,
                password=password,
                auto_bind=True,
                authentication=NTLM,
            )
        except (LDAPBindError, LDAPSocketOpenError):
            raise AuthenticationError
        except:
            print("ldap", sys.exc_info()[0])
            raise AuthenticationError
