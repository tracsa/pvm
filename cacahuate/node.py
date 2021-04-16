''' This file defines some basic classes that map the behaviour of the
equivalent xml nodes '''
from case_conversion import pascalcase
from jinja2 import Template, TemplateError
import logging
import re
import requests
from jsonpath_rw import parse as jsonpathparse
import json

from cacahuate.errors import InconsistentState, MisconfiguredProvider
from cacahuate.errors import InvalidInputError, InputError, RequiredListError
from cacahuate.errors import RequiredDictError
from cacahuate.errors import ValidationErrors, RequiredInputError, EndOfProcess
from cacahuate.grammar import Condition, ConditionTransformer
from cacahuate.http.errors import BadRequest
from cacahuate.inputs import make_input
from cacahuate.jsontypes import Map, SortedMap
from cacahuate.mongo import make_context
from cacahuate.templates import render_or
from cacahuate.models import get_or_create_user
from cacahuate.imports import user_import
from cacahuate.xml import get_text, NODES, Xml
from cacahuate.cascade import cascade_invalidate, track_next_node

LOGGER = logging.getLogger(__name__)


class AuthParam:

    def __init__(self, element):
        self.name = element.getAttribute('name')
        self.value = get_text(element)
        self.type = element.getAttribute('type')


class Form:

    def __init__(self, element, context=None):
        if not context:
            context = {}

        self.ref = element.getAttribute('id')
        self.multiple = self.calc_range(element.getAttribute('multiple'))

        # Load inputs
        self.inputs = []

        for input_el in element.getElementsByTagName('input'):
            self.inputs.append(make_input(input_el, context))

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

        return Form.state_json(self.ref, collected_inputs)

    @staticmethod
    def state_json(ref, inputs, state='valid'):
        return {
            '_type': 'form',
            'state': state,
            'ref': ref,
            'inputs': SortedMap(inputs, key='name').to_json(),
        }


class Node:
    ''' An XML tag that represents an action or instruction for the virtual
    machine '''

    def __init__(self, element, xmliter, *args, **kwargs):
        for attrname, value in element.attributes.items():
            setattr(self, attrname, value)

    def is_async(self):
        raise NotImplementedError('Must be implemented in subclass')

    def validate_input(self, json_data):
        raise NotImplementedError('Must be implemented in subclass')

    def next(self, xml, state, mongo, config, *, skip_reverse=False):
        # Return next node by simple adjacency
        xmliter = iter(xml)
        xmliter.find(lambda e: e.getAttribute('id') == self.id)

        return make_node(xmliter.next_skipping_elifelse(), xmliter)

    def dependent_refs(self, invalidated, node_state):
        raise NotImplementedError('Must be implemented in subclass')

    def in_state(self, ref, node_state):
        ''' returns true if this ref is part of this state '''
        n, user, form, field = ref.split('.')

        i, ref = form.split(':')

        try:
            forms = node_state['actors']['items'][user]['forms']
            forms[int(i)]['inputs']['items'][field]

            return True
        except IndexError:
            return False
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

    # Interpolate name
    def get_name(self, context={}):
        return render_or(self._name, self._name, context)

    def set_name(self, name):
        self._name = name

    name = property(get_name, set_name)

    def name_template(self):
        return self._name

    # Interpolate description
    def get_description(self, context={}):
        return render_or(self._description, self._description, context)

    def set_description(self, description):
        self._description = description

    description = property(get_description, set_description)

    def description_template(self):
        return self._description


class FullyContainedNode(Node):
    ''' this type of node can load all of the xml element to memory as oposed
    to nodes that contain blocks of nodes, thus not being able of loading
    themselves to memory from the begining '''

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        xmliter.parser.expandNode(element)


class UserAttachedNode(FullyContainedNode):
    ''' Types of nodes that require human interaction, thus being asyncronous
    and containing a common structure like auth-filter and node-info
    '''

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

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

    def resolve_params(self, state, config):
        computed_params = {}

        context = make_context(state or {}, config)

        for param in self.auth_params:
            if state is not None and param.type == 'ref':
                element_ref, req = param.value.split('#')

                if element_ref == 'user':
                    value = state['actors'][req]

                elif element_ref == 'form':
                    try:
                        _form, _input = req.split('.')

                        value = context[_form][_input]
                    except ValueError:
                        value = None
            else:
                value = render_or(param.value, param.value, context)

            computed_params[param.name] = value

        return computed_params

    def get_actors(self, config, state):
        HiPro = user_import(
            self.auth_backend,
            'HierarchyProvider',
            config['CUSTOM_HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
            config['ENABLED_HIERARCHY_PROVIDERS'],
        )

        hierarchy_provider = HiPro(config)

        users = hierarchy_provider.find_users(
            **self.resolve_params(state, config)
        )

        def render_users(user):
            try:
                identifier, data = user
                if type(identifier) != str:
                    raise ValueError
                if type(data) != dict:
                    raise ValueError
            except ValueError:
                raise MisconfiguredProvider(
                    'User returned by hierarchy provider is not in the form '
                    '("identifier", "data"), got: {user}'.format(user=user)
                )

            return get_or_create_user(identifier, data)

        return list(map(render_users, users))


class Action(UserAttachedNode):
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element, xmliter, context=None, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        # Form resolving
        self.form_array = []

        form_array = element.getElementsByTagName('form-array')

        if len(form_array) > 0:
            for form_el in form_array[0].getElementsByTagName('form'):
                self.form_array.append(Form(form_el, context=context))

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

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        # Dependency resolving
        self.dependencies = []

        deps_node = element.getElementsByTagName('dependencies')

        if len(deps_node) > 0:
            for dep_node in deps_node[0].getElementsByTagName('dep'):
                self.dependencies.append(get_text(dep_node))

    def is_async(self):
        return True

    def next(self, xml, state, mongo, config, *, skip_reverse=False):
        context = make_context(state, config)

        if skip_reverse or context[self.id]['response'] == 'accept':
            return super().next(xml, state, mongo, config)

        state_updates = cascade_invalidate(
            xml,
            state,
            context[self.id]['inputs'],
            context[self.id]['comment']
        )

        # update state
        collection = mongo[config['EXECUTION_COLLECTION']]
        collection.update_one({
            'id': state['id'],
        }, {
            '$set': state_updates,
        })

        # reload state
        state = next(collection.find({'id': state['id']}))

        first_invalid_node = track_next_node(xml, state, mongo, config)

        return first_invalid_node

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

            if any([
                type(json_data['inputs']) is not list,
                len(json_data['inputs']) == 0,
            ]):
                raise RequiredListError('inputs', 'request.body.inputs')

            for index, field in enumerate(json_data['inputs']):
                errors = []
                try:
                    self.validate_field(field, index)
                except InputError as e:
                    errors.append(e.to_json())

                if errors:
                    raise BadRequest(errors)

            if 'comment' not in json_data:
                raise RequiredInputError('comment', 'request.body.comment')

            if type(json_data['comment']) is not str:
                raise BadRequest([{
                    'detail': '\'comment\' must be a str',
                    'code': 'validation.invalid',
                    'where': 'request.body.comment',
                }])

        return [Form.state_json(self.id, [
            {
                'name': 'response',
                'value': json_data['response'],
                'value_caption': json_data['response'],
            },
            {
                'name': 'comment',
                'value': json_data['comment'],
                'value_caption': json_data['comment'],
            },
            {
                'name': 'inputs',
                'value': json_data.get('inputs'),
                'value_caption': json.dumps(json_data.get('inputs')),
            },
        ])]

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

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

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
            return render_or(self.value, self.value, context)


class CallForm(Node):

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.inputs = []

        for input_el in element.getElementsByTagName('input'):
            self.inputs.append(CallFormInput(input_el, xmliter))

    def render(self, context):
        res = {
            'ref': self.ref,
            'data': {
            },
        }

        for input in self.inputs:
            res['data'][input.name] = input.render(context)

        return res


class Call(FullyContainedNode):
    ''' Calls a subprocess '''

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.name = 'Call ' + self.id
        self.description = 'Call ' + self.id

        self.procname = get_text(element.getElementsByTagName('procname')[0])

        self.forms = []

        data_el = element.getElementsByTagName('data')[0]

        for form_el in data_el.getElementsByTagName('form'):
            self.forms.append(CallForm(form_el, xmliter))

    def is_async(self):
        return False

    def work(self, config, state, channel, mongo):
        xml = Xml.load(config, self.procname)

        xmliter = iter(xml)
        node = make_node(next(xmliter), xmliter)
        context = make_context(state, config)

        data = {
            'form_array': [f.render(context) for f in self.forms],
        }

        collected_input = node.validate_input(data)

        xml.start(node, collected_input, mongo, channel, '__system__')

        return []

    def dependent_refs(self, invalidated, node_state):
        return set()


class Exit(FullyContainedNode):
    ''' A node that kills an execution with some status '''

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.name = 'Exit ' + self.id
        self.description = 'Exit ' + self.id

    def is_async(self):
        return False

    def next(self, xml, state, mongo, config, *, skip_reverse=False):
        raise EndOfProcess

    def work(self, config, state, channel, mongo):
        return []


class Conditional(Node):

    def __init__(self, element, xmliter, type='IF', *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.name = type + ' ' + self.id
        self.description = type + ' ' + self.id

        self.condition = xmliter.get_next_condition()

    def is_async(self):
        return False

    def next(self, xml, state, mongo, config, *, skip_reverse=False):
        xmliter = iter(xml)

        # consume up to this node
        ifnode = xmliter.find(lambda e: e.getAttribute('id') == self.id)

        if not make_context(state, config)[self.id]['condition']:
            xmliter.expand(ifnode)

        return make_node(xmliter.next_skipping_elifelse(), xmliter)

    def work(self, config, state, channel, mongo):
        tree = Condition().parse(self.condition)

        try:
            value = ConditionTransformer(make_context(state, config)).transform(tree)
        except ValueError as e:
            raise InconsistentState('Could not evaluate condition: {}'.format(
                str(e)
            ))

        return [Form.state_json(self.id, [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': value,
                'value_caption': str(value),
            }
        ])]

    def dependent_refs(self, invalidated, node_state):
        ''' IF nodes should alwas be invalidated in case the value they depend
        on changes, so this function just returns this node's ref'''
        actor = next(iter(node_state['actors']['items'].keys()))

        return {'{node}.{actor}.0:approval.condition'.format(
            node=self.id,
            actor=actor,
        )}


class If(Conditional):

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, 'IF', *args, **kwargs)


class Elif(Conditional):

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, 'ELIF', *args, **kwargs)


class Else(Node):

    def is_async(self):
        return False

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.name = 'ELSE ' + self.id
        self.description = 'ELSE ' + self.id

    def work(self, config, state, channel, mongo):
        return [Form.state_json(self.id, [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': True,
                'value_caption': 'True',
            },
        ])]

    def dependent_refs(self, invalidated, node_state):
        ''' ELSE nodes should alwas be invalidated in case the value they depend
        on changes, so this function just returns this node's ref'''
        actor = next(iter(node_state['actors']['items'].keys()))

        return {'{node}.{actor}.0:approval.condition'.format(
            node=self.id,
            actor=actor,
        )}


class CaptureValue:

    def __init__(self, element):
        self.path = element.getAttribute('path')
        self.name = element.getAttribute('name')
        self.label = element.getAttribute('label')
        self.type = element.getAttribute('type')

    def capture(self, data, parentpath):
        if parentpath:
            path = '{}.{}'.format(parentpath, self.path)
        else:
            path = self.path

        try:
            value = jsonpathparse(path).find(data)[0].value
        except IndexError:
            raise ValueError('Could not match value')

        return {
            'name': self.name,
            'value': value,
            'type': self.type,
            'label': self.label,
            'value_caption': str(value),
        }


class Capture:

    def __init__(self, element):
        self.id = element.getAttribute('id')
        self.multiple = bool(element.getAttribute('multiple'))
        self.path = element.getAttribute('path')

        self.values = [
            CaptureValue(value)
            for value in element.getElementsByTagName('value')
        ]

    def capture(self, data):
        if self.multiple:
            return self.capture_multiple(data)

        return [{
            'id': self.id,
            'items': [
                value.capture(data, self.path) for value in self.values
            ],
        }]

    def capture_multiple(self, data):
        try:
            match = jsonpathparse(self.path).find(data)[0]
        except IndexError:
            raise ValueError('Did not find a match with that path')

        return [
            {
                'id': self.id,
                'items': [
                    value.capture(localdata, None) for value in self.values
                ],
            }
            for localdata in match.value
        ]

    def __str__(self):
        return '<Capture id="{}" path="{}">'.format(self.id, self.path)


class Request(FullyContainedNode):
    ''' A node that makes a TCP Request '''

    def __init__(self, element, xmliter, *args, **kwargs):
        super().__init__(element, xmliter, *args, **kwargs)

        self.name = 'Request ' + self.id
        self.description = 'Request ' + self.id
        self.url = get_text(element.getElementsByTagName('url')[0])

        # Body and headers
        try:
            self.body = get_text(element.getElementsByTagName('body')[0])
        except IndexError:
            self.body = ''

        self.headers = []

        for header in element.getElementsByTagName('header'):
            self.headers.append(
                (header.getAttribute('name'), get_text(header))
            )

        # Captures
        try:
            self.capture_type = element.getElementsByTagName(
                'captures'
            )[0].getAttribute('type')
        except IndexError:
            self.capture_type = None  # Indicates no capture

        self.captures = [
            Capture(capture)
            for capture in element.getElementsByTagName('capture')
        ]

        # Dependency resolving
        self.dependencies = []

        deps_node = element.getElementsByTagName('dependencies')

        if len(deps_node) > 0:
            for dep_node in deps_node[0].getElementsByTagName('dep'):
                self.dependencies.append(get_text(dep_node))

    def make_request(self, context):
        data_forms = []

        try:
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

            data_forms.append({
                'id': self.id,
                'items': [
                    {
                        'name': 'status_code',
                        'value': response.status_code,
                        'type': 'int',
                        'label': 'Status Code',
                        'value_caption': str(response.status_code),
                    },
                    {
                        'name': 'raw_response',
                        'value': response.text,
                        'type': 'text',
                        'label': 'Response',
                        'value_caption': response.text,
                    }
                ],
            })

            # Capture request data if specified
            if self.capture_type is not None:
                if self.capture_type == 'json':
                    data = response.json()
                else:
                    raise NotImplementedError('Only json captures joven')

                for capture in self.captures:
                    for form in capture.capture(data):
                        data_forms.append(form)
        except TemplateError:
            data_forms.append({
                'id': self.id,
                'items': [
                    {
                        'name': 'status_code',
                        'value': 0,
                        'type': 'int',
                        'label': 'Status Code',
                        'value_caption': '0',
                    },
                    {
                        'name': 'raw_response',
                        'value': 'Jinja error prevented this request',
                        'type': 'text',
                        'label': 'Response',
                        'value_caption': 'Jinja error prevented this request',
                    }
                ],
            })
        except requests.exceptions.ConnectionError as e:
            data_forms.append({
                'id': self.id,
                'items': [
                    {
                        'name': 'status_code',
                        'value': 0,
                        'type': 'int',
                        'label': 'Status Code',
                        'value_caption': '0',
                    },
                    {
                        'name': 'raw_response',
                        'value': str(e),
                        'type': 'text',
                        'label': 'Response',
                        'value_caption': str(e),
                    }
                ],
            })

        return data_forms

    def work(self, config, state, channel, mongo):
        data_forms = self.make_request(make_context(state, config))

        return [
            Form.state_json(data_form['id'], [
                {
                    'name': item['name'],
                    'state': 'valid',
                    'type': item['type'],
                    'value': item['value'],
                    'label': item['label'],
                    'value_caption': item['value_caption'],
                    'hidden': False,
                }
                for item in data_form['items']
            ])
            for data_form in data_forms
        ]

    def is_async(self):
        return False

    def in_dependencies(self, ref):
        node, user, form, field = ref.split('.')
        index, ref = form.split(':')
        fref = ref + '.' + field

        for dep in self.dependencies:
            if dep == fref:
                return True

        return False

    def dependent_refs(self, invalidated, node_state):
        ''' finds dependencies of the invalidated set in this node '''
        refs = set()
        actor = next(iter(node_state['actors']['items'].keys()))

        for inref in invalidated:
            if self.in_dependencies(inref):
                refs.add('{node}.{actor}.0:{node}.status_code'.format(
                    node=self.id,
                    actor=actor,
                ))

        return refs


def make_node(element, xmliter, context=None) -> Node:
    if not context:
        context = {}

    ''' returns a build Node object given an Element object '''
    if element.tagName not in NODES:
        raise ValueError(
            'Class definition not found for node: {}'.format(element.tagName)
        )

    class_name = pascalcase(element.tagName)
    available_classes = __import__(__name__).node

    return getattr(available_classes, class_name)(element, xmliter, context)
