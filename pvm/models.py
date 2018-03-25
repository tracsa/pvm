from coralillo import Model, fields


class Execution(Model):
    process_name = fields.Text()
    pointers     = fields.SetRelation('pvm.models.Pointer', inverse='execution')
    actors       = fields.Dict()
    documents    = fields.Dict()
    forms        = fields.Dict()


class Pointer(Model):
    node_id   = fields.Text()
    execution = fields.ForeignIdRelation(Execution, inverse='pointers')


class User(Model):
    identifier = fields.Text(index=True)
    tokens     = fields.SetRelation('pvm.models.Token', inverse='user')


class Token(Model):
    token = fields.Text(index=True)
    user  = fields.ForeignIdRelation(User, inverse='tokens')


def bind_models(engine):
    Execution.set_engine(engine)
    Pointer.set_engine(engine)
    User.set_engine(engine)
    Token.set_engine(engine)
