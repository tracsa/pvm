from case_conversion import pascalcase
from datetime import datetime
from functools import reduce
from operator import and_
import ast

from cacahuate.errors import ValidationErrors, RequiredInputError, \
    HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from cacahuate.xml import get_text

INPUTS = [
    'text',
    'password',
    'checkbox',
    'radio',
    'file',
    'datetime',
    'date',
    'select',
    'hidden',
]


class Option:

    def __init__(self, element):
        self.label = get_text(element)
        self.value = element.getAttribute('value')

    def to_json(self):
        return {
            'label': self.label,
            'value': self.value,
        }


class Input:
    """docstring for Input"""

    def __init__(self, element):
        self.type = element.getAttribute('type')
        self.required = element.getAttribute('required') == 'required'
        self.name = element.getAttribute('name')
        self.default = element.getAttribute('default') or None
        self.label = element.getAttribute('label') or self.name

        self.dependencies = []

        deps_el = element.getElementsByTagName('dependencies')

        if deps_el:
            for dep_el in deps_el[0].getElementsByTagName('dep'):
                self.dependencies.append(get_text(dep_el))

    def validate(self, value, form_index):
        value = value or self.get_default()

        if self.required and (value == '' or value is None):

            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )
        return value

    def get_default(self):
        return self.default

    def make_caption(self, value):
        return value

    def to_json(self):
        return {
            'type': self.type,
            'name': self.name,
            'label': self.label,
            'value': None,
            'value_caption': None,
        }


class TextInput(Input):
    pass

class HiddenInput(Input):
    pass


class PasswordInput(TextInput):
    pass


class FiniteOptionInput(Input):

    def __init__(self, element):
        super().__init__(element)

        self.options = []

        opttag = element.getElementsByTagName('options')

        if len(opttag) > 0:
            for opt in opttag[0].getElementsByTagName('option'):
                self.options.append(Option(opt))

    def __contains__(self, item):
        for opt in self.options:
            if opt.value == item:
                return True

        return False

    def to_json(self):
        json_data = super().to_json()

        json_data['options'] = list(map(
            lambda o: o.to_json(),
            self.options
        ))

        return json_data


class CheckboxInput(FiniteOptionInput):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        if value is None:
            value = []
        if type(value) == str:
            value = ast.literal_eval(value)
        if type(value) is not list:
            raise RequiredListError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, value)
            )

        for val in value:
            if val not in self:
                raise InvalidInputError(
                    self.name,
                    'request.body.form_array.{}.{}'.format(
                        form_index,
                        self.name
                    )
                )

        return value


class RadioInput(FiniteOptionInput):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        if type(value) is not str and value is not None:
            raise RequiredStrError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        if value not in self:

            raise InvalidInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return value


class SelectInput(RadioInput):
    pass


class FileInput(Input):

    def __init__(self, element):
        super().__init__(element)

        self.provider = element.getAttribute('provider')

    def validate(self, value, form_index):
        super().validate(value, form_index)

        if not value:
            value = None

        if value is not None and type(value) is not dict:
            raise InvalidInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        provider = self.provider

        if not value and self.required:
            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        if provider == 'doqer':
            if value is not None:
                valid = reduce(
                    and_,
                    map(
                        lambda attr: attr in value and value[attr] is not None,
                        ['id', 'mime', 'name', 'type']
                    )
                )

                if not valid:
                    raise InvalidInputError(
                        self.name,
                        'request.body.form_array.{}.{}'.format(
                            form_index,
                            self.name
                        )
                    )
        else:
            abort(500, 'File provider `{}` not implemented'.format(provider))

        return value


class DatetimeInput(Input):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        value = value or self.get_default()

        if not value and self.required:
            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise InvalidDateError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return value

    def get_default(self):
        if self.default == 'now':
            return datetime.now().isoformat() + 'Z'

        return ''


class DateInput(DatetimeInput):
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
