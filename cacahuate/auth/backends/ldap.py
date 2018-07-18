from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError

from cacahuate.auth.base import BaseAuthProvider
from cacahuate.errors import AuthFieldRequired, AuthFieldInvalid


class LdapAuthProvider(BaseAuthProvider):

    def authenticate(self, **credentials):
        if 'username' not in credentials or not credentials['username']:
            raise AuthFieldRequired('username')
        if 'password' not in credentials or not credentials['password']:
            raise AuthFieldRequired('password')

        server_uri = self.config['LDAP_URI']
        use_ssl = self.config['LDAP_SSL']
        base = self.config['LDAP_BASE']
        domain = self.config['LDAP_DOMAIN']

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
            raise AuthFieldInvalid('password')

        conn.search(
            base,
            '(CN={})'.format(username),
            attributes=['mail', 'givenName', 'sn']
        )

        entry = conn.entries[0]

        identifier = '{}\\{}'.format(domain, username)
        email = str(entry.mail)
        name = str(entry.givenName)
        surname = str(entry.sn)
        fullname = '{} {}'.format(name, surname)

        return (identifier, {
            'identifier': identifier,
            'email': email,
            'fullname': fullname,
        })
