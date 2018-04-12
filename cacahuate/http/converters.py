from flask import abort
from importlib import import_module
from werkzeug.routing import BaseConverter
import case_conversion
import os
import sys

from cacahuate.errors import MisconfiguredProvider
from cacahuate.http.errors import NotFound
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import


class AuthProviderConverter(BaseConverter):

    def to_python(self, value):
        try:
            cls = user_import(
                value,
                'AuthProvider',
                app.config['LOGIN_PROVIDERS'],
                'cacahuate.auth.backends',
            )
        except MisconfiguredProvider as e:
            abort(500, str(e))

        return cls(app.config)

    def to_url(self, values):
        raise NotImplementedError('this converter does not work backwards')


app.url_map.converters['AuthProvider'] = AuthProviderConverter
