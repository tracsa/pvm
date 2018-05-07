from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPCursorError

from cacahuate.auth.base import BaseAuthProvider, BaseUser
from cacahuate.errors import AuthenticationError
from cacahuate.http.wsgi import app


class LdapUser(BaseUser):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_identifier(self):
        return self.username

    def get_human_name(self):
        return self.fullname

    def get_x_info(self, notification_backend):
        return getattr(self, notification_backend)


class LdapAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or \
           'password' not in credentials:
            raise AuthenticationError

        server_uri = app.config['LDAP_URI']
        use_ssl = app.config['LDAP_SSL']
        base = app.config['LDAP_BASE']
        domain = app.config['LDAP_DOMAIN']

        # Use credentials to authenticate
        username = credentials['username']
        password = credentials['password']
        if 'domain' in credentials:
            domain = credentials['DOMAIN']

        # Connect & query ldap
        server = Server(
            server_uri,
            get_info=ALL,
            use_ssl=use_ssl,
        )

        try:
            conn = Connection(
                server,
                user='{}\\{}'.format(domain, username),
                password=password,
                auto_bind=True,
            )
        except LDAPBindError:
            raise AuthenticationError

        conn.search(base, '(CN={})'.format(username), attributes=['mail', 'givenName', 'sn'])

        entry = conn.entries[0]

        email = str(entry.mail)
        name = str(entry.givenName)
        surname = str(entry.sn)
        fullname = '{} {}'.format(name, surname)

        return LdapUser(
            username='{}\\{}'.format(domain, username),
            email=email,
            fullname=fullname,
        )
