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
import case_conversion

from cacahuate.errors import ValidationErrors, InputError,\
    RequiredInputError, HierarchyError, InvalidDateError, InvalidInputError, \
    RequiredListError, RequiredStrError, MisconfiguredProvider
from cacahuate.http.errors import BadRequest, Unauthorized, Forbidden
from cacahuate.models import User, Token
from cacahuate.xml import input_to_dict, get_form_specs
from cacahuate.http.wsgi import app
from cacahuate.utils import user_import
from cacahuate import inputs


def validate_input(form_index: int, input, value):
    ''' Validates the given value against the requirements specified by the
    input element '''
    input_type = input.get('type')

    cls = getattr(
        inputs,
        case_conversion.pascalcase(input_type) + 'Input'
    )
    instance = cls(form_index, input)

    res = {**input}

    res['value'] = instance.validate(value)

    return res


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
    collected_inputs = []

    for input in form_specs.inputs:
        try:
            input_description = validate_input(
                index,
                input,
                data.get(input.name),
            )
            collected_inputs.append(input_description)
        except InputError as e:
            errors.append(e)

    if errors:
        raise ValidationErrors(errors)

    return collected_inputs


def validate_form_spec(form_specs, data) -> dict:
    ''' Validates the given data against the spec contained in form. In case of
    failure raises an exception. In case of success returns the validated data.
    '''
    collected_specs = []

    if form_specs.multiple:
        max = float('inf')
        min = 0
    else:
        max = 1
        min = 1

    for index, form in get_associated_data(form_specs.ref, data, min, max):
        collected_specs.append(validate_form(
            form_specs,
            index,
            form.get('data', {})
        ))

    return collected_specs


def validate_forms(node, json_data):
    if 'form_array' in json_data and type(json_data['form_array']) != list:
        raise BadRequest({
            'detail': 'form_array has wrong type',
            'where': 'request.body.form_array',
        })

    collected_forms = []
    errors = []

    for form in node.form_array:
        try:
            for data in validate_form_spec(form, json_data):
                # because a form might have multiple responses
                collected_forms.append((form['ref'], data))
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
    if not node.auth_backend:
        return

    try:
        HiPro = user_import(
            node.auth_backend,
            'HierarchyProvider',
            app.config['HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
        )
    except MisconfiguredProvider:
        abort(500, 'Misconfigured hierarchy provider, sorry')

    hipro = HiPro(app.config)

    try:
        hipro.validate_user(user, **node.resolve_params(execution))
    except HierarchyError:
        raise Forbidden([{
            'detail': 'The provided credentials do not match the specified'
                      ' hierarchy',
            'where': 'request.authorization',
        }])
