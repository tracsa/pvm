from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from datetime import datetime
from functools import reduce
from operator import and_
import ast


class Input(object):
    """docstring for Input"""
    def __init__(self, form_index: int, input):
        self.form_index = form_index
        self.input = input
        self.input_type = input.get('type')
        self.value = ''

    def validate(self, value):
        self.value = value
        if self.input.get('required')\
           and (self.value == '' or self.value is None):
                raise RequiredInputError(
                    self.form_index,
                    self.input.get('name')
                )
        if not self.input.get('required') and self.input.get('default'):
            self.value = self.get_default()

        if not self.input.get('required') and not self.input.get('default'):

            self.value = self.get_value()

    def get_default(self):
        return self.input.get('default')

    def get_value(self):
        return self.input.get('value')


class TextInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(self.value) is not str:
            raise RequiredStrError(self.form_index, value)
        return self.value


class PasswordInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(self.value) is not str:
            raise RequiredStrError(self.form_index, value)
        return self.value


class CheckboxInput(Input):
    def validate(self, value):
        super().validate(value)

        if type(self.value) == str:
            self.value = ast.literal_eval(self.value)
        if type(self.value) is not list:
            raise RequiredListError(self.form_index, self.value)

        list_values = [
            child_element.get('value')
            for child_element in self.input.get('options', [])
        ]

        for val in self.value:
            if val not in list_values:
                raise InvalidInputError(
                    self.form_index,
                    self.input.get('name')
                )
        return self.value


class RadioInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(self.value) is not str:
            raise RequiredStrError(self.form_index, self.input.get('name'))

        list_values = [
            child_element.get('value')
            for child_element in self.input.get('options', [])
        ]
        if self.value not in list_values:
            raise InvalidInputError(self.form_index, self.input.get('name'))
        return self.value


class FileInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(value) is not dict:
            raise InvalidInputError(self.form_index, self.input.get('name'))

        provider = self.input.get('provider')
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
                    self.input.get('name')
                )
        else:
            abort(500, 'File provider `{}` not implemented'.format(provider))
        return value


class DatetimeInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(self.value) is not str:
            raise RequiredStrError(self.form_index, self.input.get('name'))

        try:
            datetime.strptime(self.value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise InvalidDateError(self.form_index, self.input.get('name'))
        return self.value


class DateInput(DatetimeInput):
    pass


class SelectInput(Input):
    def validate(self, value):
        super().validate(value)
        if type(self.value) is not str:
            raise RequiredStrError(self.form_index, self.input.get('name'))

        list_values = [
            child_element.get('value')
            for child_element in self.input.get('options', [])
        ]

        if self.value not in list_values:
            raise InvalidInputError(self.form_index, self.input.get('name'))
        return self.value
