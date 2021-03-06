from os import path

from coralillo.errors import ModelNotFoundError
from flask import make_response
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cacahuate.http.mongo import mongo
from cacahuate.http.wsgi import app
from cacahuate.mongo import make_context


def datetimeformat(value, format='%Y-%m-%d %H:%M:%S%z'):
    return value.strftime(format)


@app.route('/v1/execution/<id>/summary', methods=['GET'])
def execution_template(id):
    # load values
    collection = mongo.db[app.config['EXECUTION_COLLECTION']]

    try:
        execution = next(collection.find({'id': id}))
    except StopIteration:
        raise ModelNotFoundError(
            'Specified execution never existed, and never will'
        )

    if 'process_name' not in execution:
        return 'Not supported for old processes', 409

    context = make_context(execution, app.config)

    # load template
    process_name = execution['process_name']
    name, version, _ = process_name.split('.')

    # Loaders will be inserted in inverse order and then reversed. The fallback
    # is the default template at ``templates/summary.html``
    paths = [
        path.join(path.dirname(path.realpath(__file__)), '../../templates'),
    ]

    if app.config['TEMPLATE_PATH'] is not None and path.isdir(app.config['TEMPLATE_PATH']):
        paths.append(app.config['TEMPLATE_PATH'])

        process_dir = path.join(app.config['TEMPLATE_PATH'], name)
        if path.isdir(process_dir):
            paths.append(process_dir)

        process_version_dir = path.join(
            process_dir, version
        )
        if path.isdir(process_version_dir):
            paths.append(process_version_dir)

    env = Environment(
        loader=FileSystemLoader(reversed(paths)),
        autoescape=select_autoescape(['html', 'xml'])
    )

    env.filters['datetimeformat'] = datetimeformat

    for name, function in app.config['JINJA_FILTERS'].items():
        env.filters[name] = function

    return make_response(
        env.get_template('summary.html').render(**context),
        200,
    )
