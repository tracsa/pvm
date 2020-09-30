from flask import abort

from cacahuate.errors import RequiredInputError, HierarchyError, \
    MisconfiguredProvider
from cacahuate.http.errors import BadRequest, Forbidden
from cacahuate.http.wsgi import app
from cacahuate.imports import user_import


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
            app.config['CUSTOM_HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
            app.config['ENABLED_HIERARCHY_PROVIDERS'],
        )
    except MisconfiguredProvider:
        abort(500, 'Misconfigured hierarchy provider, sorry')

    hipro = HiPro(app.config)

    try:
        hipro.validate_user(user, **node.resolve_params(state, app.config))
    except HierarchyError:
        raise Forbidden([{
            'detail': 'The provided credentials do not match the specified'
                      ' hierarchy',
            'where': 'request.authorization',
        }])
