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


def validate_json(json_data: dict, req: list):
    errors = []

    for item in req:
        if item not in json_data:
            errors.append(RequiredInputError(
                item,
                'request.body.{}'.format(item)
            ).to_json())

    if errors:
        raise BadRequest(errors)


def validate_auth(node, user, state=None):
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
        hipro.validate_user(user, **node.resolve_params(state))
    except HierarchyError:
        raise Forbidden([{
            'detail': 'The provided credentials do not match the specified'
                      ' hierarchy',
            'where': 'request.authorization',
        }])
