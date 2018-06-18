from coralillo.errors import BadField


class EndOfProcess(Exception):
    pass


class AuthenticationError(Exception):

    def __init__(self, json):
        super().__init__(json['detail'])
        self.json = json

    def to_json(self):
        return self.json


class AuthFieldRequired(AuthenticationError):

    def __init__(self, fieldname):
        super().__init__({
            'detail': '{} is required'.format(fieldname),
            'where': 'request.body.{}'.format(fieldname),
            'code': 'validation.required',
        })


class AuthFieldInvalid(AuthenticationError):

    def __init__(self, fieldname):
        super().__init__({
            'detail': '{} is invalid'.format(fieldname),
            'where': 'request.body.{}'.format(fieldname),
            'code': 'validation.invalid',
        })


class ProcessNotFound(Exception):
    pass


class ElementNotFound(Exception):
    pass


class CannotMove(Exception):
    pass


class RefNotFound(Exception):
    pass


class MalformedProcess(Exception):
    pass


class HierarchyError(Exception):
    pass


class IncompleteBranch(Exception):
    pass


class MisconfiguredProvider(Exception):
    pass


class InconsistentState(Exception):
    pass


class NoPointerAlive(BadField):
    message = '{field} does not have a live pointer'
    errorcode = 'no_live_pointer'


class InputError(Exception):
    detail = None
    code = None

    def __init__(self, input, where):
        self.input = input
        self.where = where

    def to_json(self):
        return {
            'detail': self.detail.format(input=self.input),
            'where': self.where,
            'code': self.code,
        }


class RequiredInputError(InputError):
    detail = "'{input}' is required"
    code = 'validation.required'


class InvalidDateError(InputError):
    detail = "'{input}' is not date time"
    code = 'validation.invalid_date'


class InvalidInputError(InputError):
    detail = "'{input}' value invalid"
    code = 'validation.invalid'


class RequiredListError(InputError):
    detail = "'{input}' must be a list"
    code = 'validation.required_list'


class RequiredDictError(InputError):
    detail = "'{input}' must be an object"
    code = 'validation.required_dict'


class RequiredStrError(InputError):
    detail = "'{input}' required a str"
    code = 'validation.required_str'


class RequiredIntError(InputError):
    detail = "'{input}' required an int"
    code = 'validation.required_int'


class RequiredFloatError(InputError):
    detail = "'{input}' required a float"
    code = 'validation.required_float'


class ValidationErrors(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors

    def to_json(self):
        return list(map(
            lambda e: e.to_json(),
            self.errors
        ))
