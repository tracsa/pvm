from coralillo.errors import BadField

class AuthenticationError(Exception): pass

class ProcessNotFound(Exception): pass

class ElementNotFound(Exception): pass

class CannotMove(Exception): pass

class DataMissing(CannotMove):

    def __init__(self, key):
        super().__init__('missing data: {}'.format(key))

class InvalidData(CannotMove):

    def __init__(self, key, value):
        super().__init__('invalid data for key {}: {}'.format(key, value))

class NoPointerAlive(BadField):
    message = '{field} does not have a live pointer'
    errorcode = 'no_live_pointer'

class InputError(Exception):

    detail = None
    code = None
    form_index = 0

    def __init__(self, form_index, input):
        self.input = input
        self.form_index = form_index

    def to_json(self):
        return {
            'detail': self.detail.format(input=self.input),
            'where': 'request.body.form_array.{}.{}'.format(
                self.form_index,
                self.input,
            ),
            'code': self.code,
        }

class RequiredInputError(InputError):

    detail = "'{input}' input is required"
    code = 'validation.required'

class ValidationErrors(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors

    def to_json(self):
        return list(map(
            lambda e:e.to_json(),
            self.errors
        ))
