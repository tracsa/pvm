from cacahuate.jsontypes import MultiFormDict


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
