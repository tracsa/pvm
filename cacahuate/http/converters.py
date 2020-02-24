from flask import abort
from werkzeug.routing import BaseConverter

from cacahuate.errors import MisconfiguredProvider
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import


class AuthProviderConverter(BaseConverter):

    def to_python(self, value):
        try:
            cls = user_import(
                value,
                'AuthProvider',
                app.config['CUSTOM_LOGIN_PROVIDERS'],
                'cacahuate.auth.backends',
                app.config['ENABLED_LOGIN_PROVIDERS'],
            )
        except MisconfiguredProvider as e:
            abort(500, str(e))

        return cls(app.config)

    def to_url(self, values):
        # TODO: KYSXD: Is this the correct way?
        return str(values)


app.url_map.converters['AuthProvider'] = AuthProviderConverter
