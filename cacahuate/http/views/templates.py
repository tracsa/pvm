from coralillo.errors import ModelNotFoundError
from flask import render_template_string, make_response, current_app as app
from datetime import datetime
import jinja2
import json
import os
from flask import Blueprint

from cacahuate.mongo import mongo
from cacahuate.utils import get_values

bp = Blueprint('summary', __name__)


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True, indent=4, separators=(',', ': '))


jinja2.environment.DEFAULT_FILTERS['pretty'] = to_pretty_json


DATE_FIELDS = [
    'started_at',
    'finished_at',
]


def json_prepare(obj):
    if obj.get('_id'):
        del obj['_id']

    for field in DATE_FIELDS:
        if obj.get(field) and type(obj[field]) == datetime:
            obj[field] = obj[field].isoformat()

    return obj


@bp.route('/v1/execution/<id>/summary', methods=['GET'])
def execution_template(id):
    # load values
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]

    try:
        exc = next(collection.find({'id': id}))
    except StopIteration:
        raise ModelNotFoundError(
            'Specified execution never existed, and never will'
        )

    execution = json_prepare(exc)

    if 'process_name' not in exc:
        return 'Not supported for old processes', 409

    # prepare default template
    default = ['<div><b>Available keys</b></div>']
    context = get_values(execution)

    for key in context:
        token = '<div>{}</div>'
        default.append(token.format(key, key))

    template_string = ''.join(default)

    # load template
    template_dir = app.config['TEMPLATE_PATH']
    process_name = execution['process_name']
    name, version, _ = process_name.split('.')

    files = os.listdir(template_dir)

    template_name = None
    for filename in files:
        try:
            fname, fversion = filename.split('.')[:2]
        except ValueError:
            # Templates with malformed name, sorry
            continue

        if fname == name and fversion == version:
            if os.path.isfile(template_dir + '/' + filename):
                template_name = filename
            elif os.path.isfile(template_dir + '/' + filename + '/template.html'):
                my_loader = jinja2.ChoiceLoader([
                    jinja2.FileSystemLoader([
                        app.config['TEMPLATE_PATH'] + '/' + filename,
                    ]),
                ])
                bp.jinja_loader = my_loader

                template_name = filename + '/template.html'

    if template_name:
        with open(os.path.join(template_dir, template_name), 'r') as contents:
            template_string = contents.read()

    # return template interpolation
    return make_response(
        render_template_string(template_string, **context),
        200,
    )
