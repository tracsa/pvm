from datetime import datetime

from cacahuate.jsontypes import MultiFormDict, Map

DATE_FIELDS = [
    'started_at',
    'finished_at',
]


def make_context(execution_data, config):
    ''' the proper and only way to get the ``'values'`` key out of
    an execution document from mongo. It takes care of the transformations
    needed for it to work in jinja templates and other contexts where the
    multiplicity of answers (multiforms) is relevant. '''
    context = {}

    try:
        for key, value in execution_data['values'].items():
            context[key] = MultiFormDict(value)
    except KeyError:
        pass

    context['_env'] = config.get('PROCESS_ENV') or {}

    return context


def json_prepare(obj):
    ''' Takes ``obj`` from a mongo collection and returns it *as is* with two
    minor changes:

    * ``_id`` key removed
    * objects of type ``datetime`` converted to their string isoformat representation
    '''
    return {
        k: v if not isinstance(v, datetime) else v.isoformat()
        for k, v in obj.items()
        if k != '_id'
    }


def pointer_entry(node, name, description, execution, pointer, notified_users=None):
    return {
        'id': pointer.id,
        'started_at': datetime.now(),
        'finished_at': None,
        'execution': execution.to_json(),
        'node': {
            'id': node.id,
            'name': name,
            'description': description,
            'type': type(node).__name__.lower(),
        },
        'actors': Map([], key='identifier').to_json(),
        'actor_list': [],
        'process_id': execution.process_name,
        'notified_users': notified_users or [],
        'state': 'ongoing',
    }
