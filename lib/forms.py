from coralillo import Form, fields


class ContinueProcess(Form):
    node_id      = fields.Text()
    execution_id = fields.Text()


def bind_forms(engine):
    ContinueProcess.set_engine(engine)
