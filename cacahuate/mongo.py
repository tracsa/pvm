from datetime import datetime

from cacahuate.jsontypes import MultiFormDict

DATE_FIELDS = [
    'started_at',
    'finished_at',
]


def get_values(execution_data):
    ''' the proper and only way to get the ``'values'`` key out of
    an execution document from mongo. It takes care of the transformations
    needed for it to work in jinja templates and other contexts where the
    multiplicity of answers (multiforms) is relevant. '''
    try:
        return {
            k: MultiFormDict(v) for k, v in execution_data['values'].items()
        }
    except KeyError:
        return dict()


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
