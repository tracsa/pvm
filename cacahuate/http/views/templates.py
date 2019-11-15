from coralillo.errors import ModelNotFoundError
from datetime import datetime
from jinja2 import Template, environment
import json
import os

from cacahuate.http.wsgi import app, mongo
from cacahuate.utils import get_values


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True, indent=4, separators=(',', ': '))


environment.DEFAULT_FILTERS['pretty'] = to_pretty_json


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


@app.route('/v1/execution/<id>/summary', methods=['GET'])
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
    default = []
    context = get_values(execution)

    for key in context:
        token = '<div><h2>{}</h2><pre>{{{{ {} | pretty }}}}</pre></div>'
        default.append(token.format(key, key))

    template = Template(''.join(default))

    # load template
    template_dir = app.config['TEMPLATE_PATH']
    process_name = execution['process_name']
    name, version, _ = process_name.split('.')

    files = os.listdir(template_dir)

    template_name = None
    for filename in files:
        try:
            fname, fversion, _ = filename.split('.')
        except ValueError:
            # Templates with malformed name, sorry
            continue

        if fname == name and fversion == version:
            template_name = filename

    if template_name:
        with open(os.path.join(template_dir, template_name), 'r') as contents:
            template = Template(contents.read())

    # return template interpolation
    return template.render(**context)
