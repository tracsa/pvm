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
from cacahuate.xml import resolve_params, input_to_dict
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import


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
    input_type = input.getAttribute('type')

    if input.getAttribute('required') and (value == '' or value is None):
        raise RequiredInputError(form_index, input.getAttribute('name'))

    elif input_type == 'datetime' or input.getAttribute('type') == 'date':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.getAttribute('name'))

        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise InvalidDateError(form_index, input.getAttribute('name'))

    elif input_type == 'checkbox':
        if type(value) is not list:
            raise RequiredListError(form_index, input.getAttribute('name'))

        list_values = [
            child_element.getAttribute('value')
            for child_element in input.getElementsByTagName('option')
        ]

        for val in value:
            if val not in list_values:
                raise InvalidInputError(
                        form_index,
                        input.getAttribute('name')
                    )

    elif input_type == 'radio':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.getAttribute('name'))

        list_values = [
                    child_element.getAttribute('value')
                    for child_element in input.getElementsByTagName('option')
                ]
        if value not in list_values:
            raise InvalidInputError(form_index, input.getAttribute('name'))

    elif input_type == 'select':
        if type(value) is not str:
            raise RequiredStrError(form_index, input.getAttribute('name'))

        list_values = [
            child_element.getAttribute('value')
            for child_element in input.getElementsByTagName('option')
        ]

        if value not in list_values:
            raise InvalidInputError(form_index, input.getAttribute('name'))

    elif input_type == 'file':
        if type(value) is not dict:
            raise InvalidInputError(form_index, input.getAttribute('name'))

        provider = input.getAttribute('provider')
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
                raise InvalidInputError(form_index, input.getAttribute('name'))
        else:
            abort(500, 'File provider `{}` not implemented'.format(provider))

    input_dict = input_to_dict(input)
    input_dict['value'] = value

    return input_dict


def validate_form(index: int, form: Element, data: dict) -> dict:
    ''' Validates the given data against the spec contained in form. In case of
    failure raises an exception. In case of success returns the validated data.
    '''
    ref = form.getAttribute('id')
    given_data = get_associated_data(ref, data)
    collected_data = []
    errors = []

    for input in form.getElementsByTagName('input'):
        name = input.getAttribute('name')

        try:
            input_description = validate_input(
                index,
                input,
                given_data.get(name)
            )
            collected_data.append(input_description)
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
            collected_forms.append((form.getAttribute('id'), data))
        except ValidationErrors as e:
            errors += e.errors

    if len(errors) > 0:
        raise BadRequest(ValidationErrors(errors).to_json())

    return collected_forms
