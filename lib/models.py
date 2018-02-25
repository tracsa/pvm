from coralillo import Model, fields


class Execution(Model):
    process_name = fields.Text()
    pointers     = fields.SetRelation('lib.models.Pointer', inverse='execution')


class Pointer(Model):
    node_id   = fields.Text()
    execution = fields.ForeignIdRelation(Execution, inverse='pointers')


def bound_models(engine):
    Execution.set_engine(engine)
    Pointer.set_engine(engine)
