from flask import abort
from importlib import import_module
from pvm.http.errors import NotFound
from pvm.http.wsgi import app
from werkzeug.routing import BaseConverter
import case_conversion


class AuthProviderConverter(BaseConverter):

    def to_python(self, value):
        try:
            mod = import_module('pvm.auth.backends.{}'.format(value))
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
