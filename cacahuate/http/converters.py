from flask import abort
from importlib import import_module
from cacahuate.http.errors import NotFound
from cacahuate.http.wsgi import app
from werkzeug.routing import BaseConverter
import case_conversion
import os
import sys


class AuthProviderConverter(BaseConverter):

    def to_python(self, value):
        # this allows custom login providers
        if value in app.config['LOGIN_PROVIDERS']:
            import_path = app.config['LOGIN_PROVIDERS'][value]

            cwd = os.getcwd()

            if cwd not in sys.path:
                sys.path.insert(0, cwd)
        else:
            import_path = 'cacahuate.auth.backends.' + value

        try:
            mod = import_module(import_path)
            cls = getattr(
                mod, case_conversion.pascalcase(value) + 'AuthProvider'
            )
        except ModuleNotFoundError:
            abort(404, 'Auth backend not found: {}'.format(value))
        except AttributeError as e:
            abort(500, 'Misconfigured auth provider, sorry')

        return cls(app.config)

    def to_url(self, values):
        raise NotImplementedError('this converter does not work backwards')


app.url_map.converters['AuthProvider'] = AuthProviderConverter
