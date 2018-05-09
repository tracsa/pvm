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


def validate_form(form_specs, index, data):
    errors = []
    collected_inputs = []

    for input in form_specs.inputs:
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


def validate_form_spec(form_specs, associated_data) -> dict:
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

    index = 0
    form_array = json_data.get('form_array', [])
    for form_specs in node.form_array:
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
            for data in validate_form_spec(form_specs, forms):
                collected_forms.append((ref, data))
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
