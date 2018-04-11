import sys
import inspect
from coralillo import Model, fields


class Execution(Model):
    ''' keeps track of the pointers and related data during a process'sss
    execution '''
    process_name = fields.Text()
    name = fields.Text()
    description = fields.Text()
    pointers = fields.SetRelation(
        'cacahuate.models.Pointer',
        inverse='execution'
    )
    actors = fields.SetRelation(
        'cacahuate.models.Activity',
        inverse='execution'
    )
    forms = fields.SetRelation(
        'cacahuate.models.Questionaire',
        inverse='execution'
    )

    def get_state(self):
        return {
            'forms': [q.get_state() for q in self.proxy.forms.get()],
            'actors': [a.get_state() for a in self.proxy.actors.get()],
        }


class Activity(Model):
    ''' relates a user and a execution '''
    execution = fields.ForeignIdRelation(
        'cacahuate.models.Execution',
        inverse='actors'
    )
    user = fields.ForeignIdRelation(
        'cacahuate.models.User',
        inverse='activities'
    )
    ref = fields.Text()

    def get_state(self):
        return {
            'ref': self.ref,
            'user_id': self.proxy.user.get().id,
        }


class Questionaire(Model):
    ''' Represents filled forms and their data '''
    ref = fields.Text()
    data = fields.Dict()
    execution = fields.ForeignIdRelation(Execution, inverse='forms')

    def get_state(self):
        return {
            'ref': self.ref,
            'data': self.data,
        }


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
    human_name = fields.Text()
    tokens = fields.SetRelation('cacahuate.models.Token', inverse='user')
    # processes I'm participating in
    activities = fields.SetRelation(
        'cacahuate.models.Activity',
        inverse='user'
    )
    # pending tasks to solve
    tasks = fields.SetRelation(
        'cacahuate.models.Pointer',
        inverse='candidates'
    )


class Token(Model):
    ''' allows a user to make requests through the api '''
    token = fields.Text(index=True)
    user = fields.ForeignIdRelation(User, inverse='tokens')


def bind_models(eng):
    for name, cls in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(cls):
            if issubclass(cls, Model):
                cls.set_engine(eng)
