from importlib import import_module
from xml.dom.minidom import Element
from case_conversion import pascalcase
from flask import request

from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError
from cacahuate.http.errors import BadRequest, Unauthorized, Forbidden
from cacahuate.models import User, Token
from cacahuate.xml import get_ref, resolve_params
from cacahuate.http.wsgi import app


def get_associated_data(ref: str, data: dict) -> dict:
    ''' given a reference returns its asociated data in the data dictionary '''
    if 'form_array' not in data:
        return {}

    for form in data['form_array']:
        if type(form) != dict:
            continue

        if 'ref' not in form:
            continue

        if form['ref'] == ref:
            return form['data']

    return {}


def validate_input(form_index: int, input: Element, value):
    ''' Validates the given value against the requirements specified by the
    input element '''
    if input.getAttribute('required') and (value == '' or value is None):
        raise RequiredInputError(form_index, input.getAttribute('name'))

    return value


def validate_form(index: int, form: Element, data: dict) -> dict:
    ''' Validates the given data against the spec contained in form. In case of
    failure raises an exception. In case of success returns the validated data.
    '''
    ref = get_ref(form)

    given_data = get_associated_data(ref, data)
    collected_data = {}
    errors = []

    for input in form.getElementsByTagName('input'):
        name = input.getAttribute('name')

        try:
            collected_data[name] = \
                validate_input(index, input, given_data.get(name))
        except InputError as e:
            errors.append(e)

    if errors:
        raise ValidationErrors(errors)

    return collected_data


def validate_json(json_data: dict, req: list):
    errors = []

    for item in req:
        if item not in json_data:
            errors.append({
                'detail': '{} is required'.format(item),
                'where': 'request.body.{}'.format(item),
                'code': 'validation.required',
            })

    if errors:
        raise BadRequest(errors)


def validate_auth(node, execution=None):
    auth = node.getElementsByTagName('auth')

    if len(auth) == 0:
        return None, None

    auth_node = auth[0]

    # Authorization required but not provided, notify
    if request.authorization is None:
        raise Unauthorized([{
            'detail': 'You must provide basic authorization headers',
            'where': 'request.authorization',
        }])

    identifier = request.authorization['username']
    token = request.authorization['password']

    user = User.get_by('identifier', identifier)
    token = Token.get_by('token', token)

    if user is None or token is None or token.proxy.user.get().id != user.id:
        raise Unauthorized([{
            'detail': 'Your credentials are invalid, sorry',
            'where': 'request.authorization',
        }])

    # check for filters for this user
    filter_q = auth_node.getElementsByTagName('filter')

    if len(filter_q) == 1:
        filter_node = filter_q[0]
        backend = filter_node.getAttribute('backend')

        mod = import_module('cacahuate.auth.hierarchy.{}'.format(backend))
        HiPro = getattr(mod, pascalcase(backend) + 'HierarchyProvider')

        hipro = HiPro(app.config)

        try:
            hipro.validate_user(user, **resolve_params(filter_node, execution))
        except HierarchyError:
            raise Forbidden([{
                'detail': 'The provided credentials do not match the specified'
                          ' hierarchy',
                'where': 'request.authorization',
            }])

    return get_ref(auth_node), user


def validate_forms(node):
    form_array = node.getElementsByTagName('form-array')
    collected_forms = []

    if len(form_array) == 0:
        return []

    form_array_node = form_array[0]

    errors = []

    for index, form in enumerate(form_array_node.getElementsByTagName('form')):
        try:
            data = validate_form(index, form, request.json)
            collected_forms.append((get_ref(form), data))
        except ValidationErrors as e:
            errors += e.errors

    if len(errors) > 0:
        raise BadRequest(ValidationErrors(errors).to_json())

    return collected_forms
