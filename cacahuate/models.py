import sys
import inspect

from coralillo import Model, fields
from coralillo.errors import ModelNotFoundError


class Execution(Model):
    ''' keeps track of the pointers and related data during a process'sss
    execution '''
    process_name = fields.Text()
    name = fields.Text()
    name_template = fields.Text(default='')
    description = fields.Text()
    description_template = fields.Text(default='')
    pointers = fields.SetRelation(
        'cacahuate.models.Pointer',
        inverse='execution'
    )
    actors = fields.SetRelation(
        'cacahuate.models.User',
        inverse='activities'
    )
    started_at = fields.Datetime()
    finished_at = fields.Datetime(required=False)
    status = fields.Text()


class Pointer(Model):
    ''' marks a node and a execution so it can continue from there '''
    node_id = fields.Text()
    name = fields.Text()
    description = fields.Text()
    execution = fields.ForeignIdRelation(Execution, inverse='pointers')
    candidates = fields.SetRelation('cacahuate.models.User', inverse='tasks')


class User(Model):
    ''' those humans who can execute actions '''
    identifier = fields.Text(index=True)
    fullname = fields.Text()
    email = fields.Text()

    tokens = fields.SetRelation('cacahuate.models.Token', inverse='user')
    # processes I'm participating in
    activities = fields.SetRelation(
        'cacahuate.models.Execution',
        inverse='actors'
    )
    # pending tasks to solve
    tasks = fields.SetRelation(
        'cacahuate.models.Pointer',
        inverse='candidates'
    )

    def get_contact_info(self, attr):
        return getattr(self, attr)


class Token(Model):
    ''' allows a user to make requests through the api '''
    token = fields.Text(index=True)
    user = fields.ForeignIdRelation(User, inverse='tokens')


def clear_username(string):
    ''' because mongo usernames have special requirements '''
    string = string.strip()

    if string.startswith('$'):
        string = string[1:]

    try:
        string = string[:string.index('@')]
    except ValueError:
        pass

    return string.replace('.', '')


def get_or_create_user(identifier, data):
    identifier = clear_username(identifier)
    data['identifier'] = identifier

    try:
        return User.get_by_or_exception('identifier', identifier)
    except ModelNotFoundError:
        return User(**data).save()


def bind_models(eng):
    for name, cls in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(cls):
            if issubclass(cls, Model):
                cls.set_engine(eng)
