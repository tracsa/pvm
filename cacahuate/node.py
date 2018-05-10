''' This file defines some basic classes that map the behaviour of the
equivalent xml nodes '''
import re
from case_conversion import pascalcase
from typing import Iterator
from xml.dom.minidom import Element

from cacahuate.errors import ElementNotFound, IncompleteBranch, \
    ValidationErrors, RequiredInputError, InvalidInputError, InputError, \
    RequiredListError, RequiredDictError
from cacahuate.grammar import Condition
from cacahuate.inputs import make_input
from cacahuate.logger import log
from cacahuate.utils import user_import
from cacahuate.xml import get_text, NODES
from cacahuate.http.errors import BadRequest


class AuthParam:

    def __init__(self, element):
        self.name = element.getAttribute('name')
        self.value = get_text(element)
        self.type = element.getAttribute('type')


class Form:

    def __init__(self, element):
        self.ref = element.getAttribute('id')
        self.multiple = self.calc_range(element.getAttribute('multiple'))

        # Load inputs
        self.inputs = []

        for input_el in element.getElementsByTagName('input'):
            self.inputs.append(make_input(input_el))

    def calc_range(self, attr):
        range = (1, 1)

        if attr:
            nums = re.compile(r'\d+').findall(attr)
            nums = list(map(lambda x: int(x), nums))
            if len(nums) == 1:
                range = (nums[0], nums[0])
            elif len(nums) == 2:
                range = (nums[0], nums[1])
            else:
                range = (0, float('inf'))

        return range

    def validate(self, index, data):
        errors = []
        collected_inputs = []

        for input in self.inputs:
            try:
                value = input.validate(
                    data.get(input.name),
                    index,
                )

                input_description = input.to_json()
                input_description['value'] = value

                collected_inputs.append(input_description)
            except InputError as e:
                errors.append(e)

        if errors:
            raise ValidationErrors(errors)

        return collected_inputs


class Node:
    ''' An XML tag that represents an action or instruction for the virtual
    machine '''

    def __init__(self, element):
        for attrname, value in element.attributes.items():
            setattr(self, attrname, value)

        # node info
        node_info = element.getElementsByTagName('node-info')

        name = ''
        description = ''

        if len(node_info) == 1:
            node_info = node_info[0]

            node_name = node_info.getElementsByTagName('name')
            name = get_text(node_name[0])

            node_description = node_info.getElementsByTagName('description')
            description = get_text(node_description[0])

        self.name = name
        self.description = description

        # Actor resolving
        self.auth_params = []
        self.auth_backend = None

        filter_q = element.getElementsByTagName('auth-filter')

        if len(filter_q) > 0:
            filter_node = filter_q[0]

            self.auth_backend = filter_node.getAttribute('backend')
            self.auth_params = list(map(
                lambda x: AuthParam(x),
                filter_node.getElementsByTagName('param')
            ))

    def is_async(self):
        raise NotImplementedError('Must be implemented in subclass')

    def validate_input(self, json_data):
        raise NotImplementedError('Must be implemented in subclass')


class Action(Node):
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element):
        super().__init__(element)

        # Form resolving
        self.form_array = []

        form_array = element.getElementsByTagName('form-array')

        if len(form_array) > 0:
            for form_el in form_array[0].getElementsByTagName('form'):
                self.form_array.append(Form(form_el))

    def is_async(self):
        return True

    def resolve_params(self, execution=None):
        computed_params = {}

        for param in self.auth_params:
            if execution is not None and param.type == 'ref':
                user_ref = param.value.split('#')[1].strip()

                try:
                    actor = next(
                        execution.proxy.actors.q().filter(ref=user_ref)
                    )

                    value = actor.proxy.user.get().identifier
                except StopIteration:
                    value = None
            else:
                value = param.value

            computed_params[param.name] = value

        return computed_params

    def get_actors(self, config, execution):
        if not self.auth_params:
            return []

        HiPro = user_import(
            self.auth_backend,
            'HierarchyProvider',
            config['HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
        )

        hierarchy_provider = HiPro(config)

        return hierarchy_provider.find_users(
            **self.resolve_params(execution)
        )

    def validate_form_spec(self, form_specs, associated_data) -> dict:
        ''' Validates the given data against the spec contained in form. In case of
        failure raises an exception. In case of success returns the validated data.
        '''
        collected_specs = []

        min, max = form_specs.multiple

        if len(associated_data) < min:
            raise BadRequest([{
                'detail': 'form count lower than expected for ref {}'.format(
                    form_specs.ref
                ),
                'where': 'request.body.form_array',
            }])

        if len(associated_data) > max:
            raise BadRequest([{
                'detail': 'form count higher than expected for ref {}'.format(
                    form_specs.ref
                ),
                'where': 'request.body.form_array',
            }])

        for index, form in associated_data:
            collected_specs.append(form_specs.validate(
                index,
                form.get('data', {})
            ))

        return collected_specs

    def validate_input(self, json_data):
        if 'form_array' in json_data and type(json_data['form_array']) != list:
            raise BadRequest({
                'detail': 'form_array has wrong type',
                'where': 'request.body.form_array',
            })

        collected_forms = []
        errors = []

        index = 0
        form_array = json_data.get('form_array', [])
        for form_specs in self.form_array:
            ref = form_specs.ref

            # Ignore unexpected forms
            while len(form_array) > index and form_array[index]['ref'] != ref:
                index += 1

            # Collect expected forms
            forms = []
            while len(form_array) > index and form_array[index]['ref'] == ref:
                forms.append((index, form_array[index]))
                index += 1

            try:
                for data in self.validate_form_spec(form_specs, forms):
                    collected_forms.append((ref, data))
            except ValidationErrors as e:
                errors += e.errors

        if len(errors) > 0:
            raise BadRequest(ValidationErrors(errors).to_json())

        return collected_forms

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
        }


class Validation(Node):

    VALID_RESPONSES = ('accept', 'reject')

    def __init__(self, element):
        super().__init__(element)

        # Dependency resolving
        self.dependencies = []

        deps_node = element.getElementsByTagName('dependencies')

        if len(deps_node) > 0:
            for dep_node in deps_node[0].getElementsByTagName('dep'):
                self.dependencies.append(get_text(dep_node))

    def validate_field(self, field, index):
        if type(field) != dict:
            raise RequiredDictError(
                'fields.{}'.format(index),
                'request.body.fields.{}'.format(index)
            )

        if 'ref' not in field:
            raise RequiredInputError(
                'fields.{}.ref'.format(index),
                'request.body.fields.{}.ref'.format(index)
            )

        if field['ref'] not in self.dependencies:
            raise InvalidInputError(
                'fields.{}.ref'.format(index),
                'request.body.fields.{}.ref'.format(index)
            )

    def validate_input(self, json_data):
        if 'response' not in json_data:
            raise RequiredInputError('response', 'request.body.response')

        if json_data['response'] not in self.VALID_RESPONSES:
            raise InvalidInputError('response', 'request.body.response')

        if json_data['response'] == 'reject':
            if 'fields' not in json_data:
                raise RequiredInputError('fields', 'request.body.fields')

            if type(json_data['fields']) is not list:
                raise RequiredListError('fields', 'request.body.fields')

            for index, field in enumerate(json_data['fields']):
                errors = []
                try:
                    self.validate_field(field, index)
                except InputError as e:
                    errors.append(e.to_json())

                if errors:
                    raise BadRequest(errors)

        return []


class Exit(Node):
    ''' A node that kills an execution with some status '''

    def is_async(self):
        return False


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if element.tagName not in NODES:
        raise ValueError(
            'Class definition not found for node: {}'.format(element.tagName)
        )

    class_name = pascalcase(element.tagName)
    available_classes = __import__(__name__).node

    return getattr(available_classes, class_name)(element)
