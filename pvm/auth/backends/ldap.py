from .base import BaseAuthProvider
from ldap3 import Server, Connection, ALL, NTLM, core
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
from pvm.errors import AuthenticationError
from pvm.http.wsgi import app
import sys


class LdapAuthProvider(BaseAuthProvider):

    def authenticate(self, username=None, password=None, domain=app.config['LDAP_DOMAIN']):
        server = Server(
            app.config['LDAP_URI'],
            get_info=ALL,
            use_ssl=app.config['LDAP_SSL'],
        )

        try:
            conn = Connection(
                server,
                user='\\'.join((domain, username)),
                password=password,
                auto_bind=True,
                authentication=NTLM,
            )
        except (LDAPBindError, LDAPSocketOpenError):
            raise AuthenticationError
        except:
            print("ldap", sys.exc_info()[0])
            raise AuthenticationError

        return {
            'user': conn.extend.standard.who_am_i()
        }
