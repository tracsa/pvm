''' This file defines some basic classes that map the behaviour of the
equivalent xml nodes '''
from case_conversion import pascalcase
from datetime import datetime
from typing import Iterator
from xml.dom.minidom import Element
from jinja2 import Template
import requests
import re

from cacahuate.errors import ElementNotFound, IncompleteBranch, \
    ValidationErrors, RequiredInputError, InvalidInputError, InputError, \
    RequiredListError, RequiredDictError
from cacahuate.inputs import make_input
from cacahuate.logger import log
from cacahuate.utils import user_import
from cacahuate.xml import get_text, NODES, Xml
from cacahuate.http.errors import BadRequest
from cacahuate.jsontypes import Map
from cacahuate.jsontypes import SortedMap


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
                input_description['value_caption'] = input.make_caption(value)
                input_description['state'] = 'valid'

                collected_inputs.append(input_description)
            except InputError as e:
                errors.append(e)

        if errors:
            raise ValidationErrors(errors)

        return {
            '_type': 'form',
            'state': 'valid',
            'ref': self.ref,
            'inputs': SortedMap(collected_inputs, key='name').to_json(),
        }


class Node:
    ''' An XML tag that represents an action or instruction for the virtual
    machine '''

    def __init__(self, element):
        for attrname, value in element.attributes.items():
            setattr(self, attrname, value)

    def is_async(self):
        raise NotImplementedError('Must be implemented in subclass')

    def validate_input(self, json_data):
        raise NotImplementedError('Must be implemented in subclass')

    def pointer_entry(self, execution, pointer, notified_users=None):
        return {
            'id': pointer.id,
            'started_at': datetime.now(),
            'finished_at': None,
            'execution': execution.to_json(),
            'node': self.to_json(),
            'actors': Map([], key='identifier').to_json(),
            'process_id': execution.process_name,
            'notified_users': notified_users or [],
        }

    def get_state(self):
        return {
            '_type': 'node',
            'type': type(self).__name__.lower(),
            'id': self.id,
            'comment': '',
            'state': 'unfilled',
            'actors': Map([], key='identifier').to_json(),
            'name': self.name,
            'description': self.description,
            'milestone': hasattr(self, 'milestone'),
        }

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': type(self).__name__.lower(),
        }


class UserAttachedNode(Node):

    def __init__(self, element):
        super().__init__(element)

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

    def resolve_params(self, state=None):
        computed_params = {}
        for param in self.auth_params:
            if state is not None and param.type == 'ref':
                element_ref, req = param.value.split('#')

                if element_ref == 'user':
                    value = state['actors'][req]

                elif element_ref == 'form':
                    try:
                        _form, _input = req.split('.')

                        value = state['values'][_form][_input]
                    except ValueError:
                        value = None
            else:
                value = param.value

            computed_params[param.name] = value

        return computed_params

    def get_actors(self, config, state):
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
            **self.resolve_params(state)
        )

    def in_state(self, ref, node_state):
        ''' returns true if this ref is part of this state '''
        n, user, form, field = ref.split('.')

        i, ref = form.split(':')

        try:
            forms = node_state['actors']['items'][user]['forms']
            forms[int(i)]['inputs']['items'][field]

            return True
        except KeyError:
            return False

    def get_invalidated_fields(self, invalidated, state):
        ''' debe devolver un conjunto de referencias a campos que deben ser
        invalidados, a partir de campos invalidados previamente '''
        node_state = state['state']['items'][self.id]

        if node_state['state'] == 'unfilled':
            return []

        found_refs = []

        for ref in invalidated:
            # for refs in this node's forms
            if self.in_state(ref, node_state):
                found_refs.append(ref)

        found_refs += self.dependent_refs(invalidated, node_state)

        return found_refs


class Action(UserAttachedNode):
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

    def dependent_refs(self, invalidated, node_state):
        ''' finds dependencies of the invalidated set in this node '''
        refs = set()
        actor = next(iter(node_state['actors']['items'].keys()))

        for dep in invalidated:
            _, depref = dep.split(':')

            for form in self.form_array:
                for field in form.inputs:
                    for dep in field.dependencies:
                        if depref == dep:
                            refs.add('{node}.{actor}.0:{form}.{input}'.format(
                                node=self.id,
                                actor=actor,
                                form=form.ref,
                                input=field.name,
                            ))

        return refs

    def validate_form_spec(self, form_specs, associated_data) -> dict:
        ''' Validates the given data against the spec contained in form.
            In case of failure raises an exception. In case of success
            returns the validated data.
        '''

        collected_forms = []

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
            if type(form) != dict:
                raise BadRequest([{
                    'detail': 'each form must be a dict',
                    'where': 'request.body.form_array.{}.data'.format(index),
                }])

            if 'data' not in form:
                raise BadRequest([{
                    'detail': 'form.data is required',
                    'code': 'validation.required',
                    'where': 'request.body.form_array.{}.data'.format(index),
                }])

            if type(form['data']) != dict:
                raise BadRequest([{
                    'detail': 'form.data must be a dict',
                    'code': 'validation.invalid',
                    'where': 'request.body.form_array.{}.data'.format(index),
                }])

            collected_forms.append(form_specs.validate(
                index,
                form['data']
            ))

        return collected_forms

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
                    collected_forms.append(data)
            except ValidationErrors as e:
                errors += e.errors

        if len(errors) > 0:
            raise BadRequest(ValidationErrors(errors).to_json())

        return collected_forms


class Validation(UserAttachedNode):

    VALID_RESPONSES = ('accept', 'reject')

    def is_async(self):
        return True

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
                'inputs.{}'.format(index),
                'request.body.inputs.{}'.format(index)
            )

        if 'ref' not in field:
            raise RequiredInputError(
                'inputs.{}.ref'.format(index),
                'request.body.inputs.{}.ref'.format(index)
            )

        try:
            node, actor, ref, input = field['ref'].split('.')
            index, ref = ref.split(':')
        except ValueError:
            raise InvalidInputError(
                'inputs.{}.ref'.format(index),
                'request.body.inputs.{}.ref'.format(index)
            )

        if not self.in_dependencies(field['ref']):
            raise InvalidInputError(
                'inputs.{}.ref'.format(index),
                'request.body.inputs.{}.ref'.format(index)
            )

    def in_dependencies(self, ref):
        node, user, form, field = ref.split('.')
        index, ref = form.split(':')
        fref = ref + '.' + field

        for dep in self.dependencies:
            if dep == fref:
                return True

        return False

    def validate_input(self, json_data):
        if 'response' not in json_data:
            raise RequiredInputError('response', 'request.body.response')

        if json_data['response'] not in self.VALID_RESPONSES:
            raise InvalidInputError('response', 'request.body.response')

        if json_data['response'] == 'reject':
            if 'inputs' not in json_data:
                raise RequiredInputError('inputs', 'request.body.inputs')

            if type(json_data['inputs']) is not list:
                raise RequiredListError('inputs', 'request.body.inputs')

            for index, field in enumerate(json_data['inputs']):
                errors = []
                try:
                    self.validate_field(field, index)
                except InputError as e:
                    errors.append(e.to_json())

                if errors:
                    raise BadRequest(errors)

        return [{
            '_type': 'form',
            'ref': 'approval',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'response': {
                        'value': json_data['response'],
                    },
                    'comment': {
                        'value': json_data['comment'],
                    },
                    'inputs': {
                        'value': json_data.get('inputs'),
                    },
                },
                'item_order': ['response', 'comment', 'inputs'],
            },
        }]

    def dependent_refs(self, invalidated, node_state):
        ''' finds dependencies of the invalidated set in this node '''
        refs = set()
        actor = next(iter(node_state['actors']['items'].keys()))

        for inref in invalidated:
            if self.in_dependencies(inref):
                refs.add('{node}.{actor}.0:approval.response'.format(
                    node=self.id,
                    actor=actor,
                ))

        return refs


class CallFormInput(Node):

    def __init__(self, element):
        super().__init__(element)

        self.value = get_text(element)
        self.type = element.getAttribute('type')

    def render(self, context):
        if self.type == 'ref':
            try:
                form_ref, input = self.value.split('#')[1].split('.')

                return context[form_ref][input]
            except ValueError:
                return None
        else:
            return self.value


class CallForm(Node):

    def __init__(self, element):
        super().__init__(element)

        self.inputs = []

        for input_el in element.getElementsByTagName('input'):
            self.inputs.append(CallFormInput(input_el))

    def render(self, context):
        res = {
            'ref': self.ref,
            'data': {
            },
        }

        for input in self.inputs:
            res['data'][input.name] = input.render(context)

        return res


class Call(Node):
    ''' Calls a subprocess '''

    def __init__(self, element):
        super().__init__(element)

        self.name = 'Call ' + self.id
        self.description = 'Call ' + self.id

        self.procname = get_text(element.getElementsByTagName('procname')[0])

        self.forms = []

        data_el = element.getElementsByTagName('data')[0]

        for form_el in data_el.getElementsByTagName('form'):
            self.forms.append(CallForm(form_el))

    def is_async(self):
        return False

    def work(self, config, state, channel, mongo):
        xml = Xml.load(config, self.procname)

        xmliter = iter(xml)
        node = make_node(next(xmliter))

        data = {
            'form_array': [f.render(state['values']) for f in self.forms],
        }

        collected_input = node.validate_input(data)

        xml.start(node, collected_input, mongo, channel, '__system__')

        return []


class Exit(Node):
    ''' A node that kills an execution with some status '''

    def __init__(self, element):
        super().__init__(element)

        self.name = 'Exit ' + self.id
        self.description = 'Exit ' + self.id

    def is_async(self):
        return False

    def work(self, config, state, channel, mongo):
        return []


class Request(Node):
    ''' A node that makes a TCP Request '''
    def __init__(self, element):
        super().__init__(element)

        urls = list(map(
            lambda e: get_text(e),
            element.getElementsByTagName('url')
        ))
        bodies = list(map(
            lambda e: get_text(e),
            element.getElementsByTagName('body')
        ))
        headers = list(map(
            lambda e: (e.getAttribute('name'), get_text(e)),
            element.getElementsByTagName('header')
        ))

        self.name = 'Request ' + self.id
        self.description = 'Request ' + self.id

        self.url = urls[0]
        self.body = bodies[0]
        self.headers = headers

    def make_request(self, context):
        url = Template(self.url).render(**context)
        body = Template(self.body).render(**context)
        headers = dict(map(
            lambda t: (t[0], Template(t[1]).render(**context)),
            self.headers
        ))

        response = requests.request(
            self.method,
            url,
            headers=headers,
            data=body
        )

        res_dict = {
            'status_code': response.status_code,
            'response': response.text,
        }

        return res_dict

    def work(self, config, state, channel, mongo):
        response = self.make_request(state['values'])

        state = [{
            '_type': 'form',
            'ref': 'request-node',
            'state': 'valid',
            'inputs': {
                '_type': ':sorted_map',
                'items': {
                    'status_code': {
                        'name': 'status_code',
                        'state': 'valid',
                        'type': 'text',
                        'value': response['status_code'],
                    },
                    'raw_response': {
                        'name': 'raw_response',
                        'state': 'valid',
                        'type': 'text',
                        'value': response['response'],
                    },
                },
                'item_order': ['status_code', 'raw_response'],
            },
        }]

        return state

    def is_async(self):
        return False


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if element.tagName not in NODES:
        raise ValueError(
            'Class definition not found for node: {}'.format(element.tagName)
        )

    # if nodes are not reflected in state
    if element.tagName == 'if':
        return None

    class_name = pascalcase(element.tagName)
    available_classes = __import__(__name__).node

    return getattr(available_classes, class_name)(element)
