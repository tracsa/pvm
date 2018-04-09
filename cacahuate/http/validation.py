from importlib import import_module
from xml.dom.minidom import Element
from flask import request, abort
import os
import sys
from datetime import datetime
from functools import reduce
from operator import and_

from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from cacahuate.http.errors import BadRequest, Unauthorized, Forbidden
from cacahuate.models import User, Token
from cacahuate.xml import resolve_params, input_to_dict, get_form_specs
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import


def validate_input(form_index: int, input, value):
    ''' Validates the given value against the requirements specified by the
    input element '''
    input_type = input.get('type')

    if input.get('required') and (value == '' or value is None):
        raise RequiredInputError(form_index, input.get('name'))

    elif input_type == 'datetime' or input.get('type') == 'date':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.get('name'))

        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise InvalidDateError(form_index, input.get('name'))

    elif input_type == 'checkbox':
        if type(value) is not list:
            raise RequiredListError(form_index, input.get('name'))

        list_values = [
            child_element.get('value')
            for child_element in input.get('options', [])
        ]

        for val in value:
            if val not in list_values:
                raise InvalidInputError(
                        form_index,
                        input.get('name')
                    )

    elif input_type == 'radio':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.get('name'))

        list_values = [
            child_element.get('value')
            for child_element in input.get('options', [])
        ]
        if value not in list_values:
            raise InvalidInputError(form_index, input.get('name'))

    elif input_type == 'select':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.get('name'))

        list_values = [
            child_element.get('value')
            for child_element in input.get('options', [])
        ]

        if value not in list_values:
            raise InvalidInputError(form_index, input.get('name'))

    elif input_type == 'file':
        if type(value) is not dict:
            raise InvalidInputError(form_index, input.get('name'))

        provider = input.get('provider')
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
                raise InvalidInputError(form_index, input.get('name'))
        else:
            abort(500, 'File provider `{}` not implemented'.format(provider))

    input['value'] = value

    return input


def get_associated_data(ref, data, min, max):
    count = 0
    forms = []

    for index, form in enumerate(data.get('form_array', [])):
        if form['ref'] == ref:
            forms.append((index, form))
            count += 1

        if count == max:
            break

    if count < min:
        raise BadRequest([{
            'detail': 'form count lower than expected for ref {}'.format(ref),
            'where': 'request.body.form_array',
        }])

    return forms


def validate_form(form_specs, index, data):
    errors = []
    collected_data = []

    for input in form_specs['inputs']:
        name = input['name']

        try:
            input_description = validate_input(
                index,
                input,
                data.get(name)
            )
            collected_data.append(input_description)
        except InputError as e:
            errors.append(e)

    if errors:
        raise ValidationErrors(errors)

    return collected_data


def validate_form_spec(form_specs, data) -> dict:
    ''' Validates the given data against the spec contained in form. In case of
    failure raises an exception. In case of success returns the validated data.
    '''
    ref = form_specs['ref']
    specs = form_specs['multiple']
    collected_data = []

    if form_specs.get('multiple'):
        max = float('inf')
        min = 0
    else:
        max = 1
        min = 1

    for index, form in get_associated_data(ref, data, min, max):
        collected_data.append((
            ref,
            validate_form(form_specs, index, form['data'])
        ))

    return collected_data


def validate_forms(node, json_data):
    if 'form_array' in json_data and type(json_data['form_array']) != list:
        raise BadRequest({
            'detail': 'form_array has wrong type',
            'where': 'request.body.form_array',
        })

    collected_forms = []
    errors = []

    for form_specs in get_form_specs(node):
        try:
            for data in validate_form_spec(form_specs, json_data):
                # because a form might have multiple responses
                collected_forms.append((form_specs['ref'], data))
        except ValidationErrors as e:
            errors += e.errors

    if len(errors) > 0:
        raise BadRequest(ValidationErrors(errors).to_json())

    return collected_forms


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


def validate_auth(node, user, execution=None):
    auth = node.getElementsByTagName('auth-filter')

    if len(auth) == 0:
        return

    auth_node = auth[0]
    backend = auth_node.getAttribute('backend')

    try:
        HiPro = user_import(
            backend,
            app.config['HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
        )
    except MisconfiguredProvider:
        abort(500, 'Misconfigured hierarchy provider, sorry')

    hipro = HiPro(app.config)

    try:
        hipro.validate_user(user, **resolve_params(auth_node, execution))
    except HierarchyError:
        raise Forbidden([{
            'detail': 'The provided credentials do not match the specified'
                      ' hierarchy',
            'where': 'request.authorization',
        }])
