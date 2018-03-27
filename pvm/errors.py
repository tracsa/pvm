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

    def __init__(self, problem):
        super().__init__()
        self.problem = problem

    def to_json(self):
        return {
            'detail': self.problem,
            'where': 'request.body.form_array',
        }

class ValidationErrors(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors

    def to_json(self):
        return list(map(
            lambda e:e.to_json(),
            self.errors
        ))
