from cacahuate.http.wsgi import app, mongo
from datetime import datetime
from jinja2 import Template, environment
import json


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
    # load template
    template_str = "{{ values }}"

    # load state
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]

    try:
        exc = next(collection.find({'id': id}))
    except StopIteration:
        raise ModelNotFoundError(
            'Specified execution never existed, and never will'
        )

    # interpolate template with state

    # return html
    return {
        'data': json_prepare(exc),
    }
