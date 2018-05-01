from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from datetime import datetime
from functools import reduce
from operator import and_
import ast
from case_conversion import pascalcase

INPUTS = [
    'text',
    'password',
    'checkbox',
    'radio',
    'file',
    'datetime',
    'date',
    'select',
]


class Input(object):
    """docstring for Input"""
    def __init__(self, element):
        self.required = element.getAttribute('required')
        self.name = element.getAttribute('name')
        self.default = element.getAttribute('default')
        self.options = element.getAttribute('options') or []
        self.provider = element.getAttribute('provider')

    def validate(self, value, form_index):
        value = value or self.get_default()

        if self.required and (value == '' or value is None):
            raise RequiredInputError(self.form_index, self.name)

        return value

    def get_default(self):
        return self.default


class TextInput(Input):
    pass


class PasswordInput(TextInput):
    pass


class CheckboxInput(Input):
    def validate(self, value):
        super().validate(value)
        if value is None:
            value = []
        if type(value) == str:
            value = ast.literal_eval(value)
        if type(value) is not list:
            raise RequiredListError(self.form_index, value)

        list_values = [
            child_element.get('value')
            for child_element in self.options
        ]

        for val in value:
            if val not in list_values:
                raise InvalidInputError(
                    self.form_index,
                    self.name
                )
        return value


class RadioInput(Input):
    def validate(self, value):
        super().validate(value)

        if type(value) is not str and value is not None:
            raise RequiredStrError(self.form_index, self.name)
        list_values = [
            child_element.get('value')
            for child_element in self.options
        ]
        if value is None:
            list_values.append(None)
        if value not in list_values:
            raise InvalidInputError(self.form_index, self.name)
        return value


class FileInput(Input):
    def validate(self, value):
        super().validate(value)
        if value is None:
            value = {}
        if type(value) is not dict:
            raise InvalidInputError(self.form_index, self.name)

        provider = self.provider
        if provider == 'doqer':
            valid = reduce(
                and_,
                map(
                    lambda attr:
                        attr in value and
                        value[attr] is not None,
                    ['id', 'mime', 'name', 'type']
                )
            )

            if not valid:
                raise InvalidInputError(
                    self.form_index,
                    self.name
                )
        else:
            abort(500, 'File provider `{}` not implemented'.format(provider))
        return value


class DatetimeInput(Input):

    def validate(self, value):
        value = value or self.get_default()

        if not value and self.required:
            raise RequiredInputError(self.form_index, self.name)

        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise InvalidDateError(self.form_index, self.name)

        return value

    def get_default(self):
        if self.default == 'now':
            return datetime.now().isoformat() + 'Z'

        return ''


class DateInput(DatetimeInput):
    pass


class SelectInput(RadioInput):
    pass


def make_input(element):
    ''' returns a build Input object given an Element object '''
    classattr = element.getAttribute('type')

    if classattr not in INPUTS:
        raise ValueError(
            'Class definition not found for input: {}'.format(classattr)
        )

    class_name = pascalcase(classattr) + 'Input'
    available_classes = __import__(__name__).inputs

    return getattr(available_classes, class_name)(element)
