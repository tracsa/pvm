from importlib import import_module
from xml.dom.minidom import Element
from flask import request, abort
import os
import sys
import ast
from datetime import datetime
from functools import reduce
from operator import and_
import json

from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from cacahuate.http.errors import BadRequest, Unauthorized, Forbidden
from cacahuate.models import User, Token
from cacahuate.xml import resolve_params, input_to_dict, get_form_specs
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import
from cacahuate.validationClass import TextInput, DateInput,\
    CheckboxInput, RadioInput, SelectInput, FileInput


def validate_input(form_index: int, input, value):
    ''' Validates the given value against the requirements specified by the
    input element '''
    input_type = input.get('type')
    if input_type == 'text' or input_type == 'password':
        text_input = TextInput(form_index, input)
        input['value'] = text_input.validate(value)
    elif input_type == 'datetime' or input_type == 'date':
        date_input = DateInput(form_index, input)
        input['value'] = date_input.validate(value)
    elif input_type == 'checkbox':
        checkbox_input = CheckboxInput(form_index, input)
        input['value'] = checkbox_input.validate(value)
    elif input_type == 'radio':
        radio_input = RadioInput(form_index, input)
        input['value'] = radio_input.validate(value)
    elif input_type == 'select':
        select_input = SelectInput(form_index, input)
        input['value'] = select_input.validate(value)
    elif input_type == 'file':
        file_input = FileInput(form_index, input)
        input['value'] = file_input.validate(value)
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
                data.get(name),
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
        collected_data.append(validate_form(form_specs, index, form['data']))

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
            'HierarchyProvider',
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
