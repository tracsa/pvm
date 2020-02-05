from case_conversion import pascalcase
from datetime import datetime
from functools import reduce
from operator import and_
import ast
import re
import numbers

from cacahuate.errors import InvalidInputError, RequiredListError
from cacahuate.errors import MisconfiguredProvider, RequiredIntError
from cacahuate.errors import RequiredFloatError, RequiredStrError
from cacahuate.errors import RequiredInputError, InvalidDateError
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
    'int',
    'float',
    'link',
    'currency',
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
        self.hidden = element.getAttribute('hidden') == 'true'

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
            'value_caption': None,  # This is computed in node.py
            'hidden': self.hidden,
        }


class TextInput(Input):
    pass


class PasswordInput(TextInput):

    def make_caption(self, value):
        return '******'


class IntInput(Input):

    def get_default(self):
        try:
            return int(self.default)
        except ValueError:
            return 0
        except TypeError:
            return 0

    def validate(self, value, form_index):
        if self.required and type(value) != int and not value:
            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        if type(value) != int and not value:
            value = self.get_default()

        try:
            value = int(value)
        except ValueError:
            raise RequiredIntError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return value

    def make_caption(self, value):
        return str(value)


class FloatInput(Input):

    def get_default(self):
        if not self.default:
            return 0

        try:
            return float(self.default)
        except ValueError:
            return 0

    def validate(self, value, form_index):
        # allowed types are None, String, and Numbers
        curated = None

        if value is None or value == '':
            curated = None
        elif isinstance(value, numbers.Number) or type(value) == str:
            try:
                curated = float(value)
            except ValueError:
                raise RequiredFloatError(
                    self.name,
                    'request.body.form_array.{}.{}'.format(
                        form_index,
                        self.name
                    )
                )
        else:
            raise RequiredFloatError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        if curated is None and self.required:
            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        if curated is None:
            curated = self.get_default()

        return curated

    def make_caption(self, value):
        return str(value)


class CurrencyInput(FloatInput):
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

    def make_caption(self, value):
        for opt in self.options:
            if opt.value == value:
                return opt.label


class CheckboxInput(FiniteOptionInput):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        if value is None:
            value = []

        if type(value) == str:
            try:
                value = ast.literal_eval(value)
            except SyntaxError:
                value = []

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

    def make_caption(self, value):
        def find_cap(val):
            for opt in self.options:
                if opt.value == val:
                    return opt.label

        return ', '.join(find_cap(val) for val in value)


class RadioInput(FiniteOptionInput):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        curated = None

        if type(value) is str:
            curated = value

        if curated not in self:
            curated = None

        if self.required and not curated:
            raise RequiredStrError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return curated


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
            raise MisconfiguredProvider(
                'File provider `{}` not implemented'.format(provider)
            )

        return value


class DatetimeInput(Input):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        value = value or self.get_default()

        if not value:
            if self.required:
                raise RequiredInputError(
                    self.name,
                    'request.body.form_array.{}.{}'.format(
                        form_index,
                        self.name
                    )
                )

            return None

        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except TypeError:
            raise InvalidDateError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )
        except ValueError:
            raise InvalidDateError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return value

    def get_default(self):
        if self.default == 'now':
            return datetime.now().isoformat() + 'Z'

        return None

    def make_caption(self, value):
        if not value:
            return

        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%c')


class DateInput(DatetimeInput):
    pass


class LinkInput(Input):

    def validate(self, value, form_index):
        super().validate(value, form_index)

        curated = None

        if not value:
            curated = None
        elif isinstance(value, dict):
            if 'label' not in value or 'href' not in value:
                raise InvalidInputError(
                    self.name,
                    'request.body.form_array.{}.{}'.format(
                        form_index,
                        self.name
                    )
                )

            label = value['label']
            href = value['href']

            link_valid = re.match('^(https?://)[a-z0-9.]+/?$', href)

            if not link_valid:
                raise InvalidInputError(
                    self.name,
                    'request.body.form_array.{}.{}'.format(
                        form_index,
                        self.name
                    )
                )

            curated = {
                'label': label,
                'href': href,
            }
        else:
            raise InvalidInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(
                    form_index,
                    self.name
                )
            )

        if not curated and self.required:
            raise RequiredInputError(
                self.name,
                'request.body.form_array.{}.{}'.format(form_index, self.name)
            )

        return curated


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
