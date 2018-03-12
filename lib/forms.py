from coralillo import Form, fields, errors
from coralillo.validation import validation_rule

from .errors import ElementNotFound


class ContinueProcess(Form):
    execution_id = fields.Text()
    node_id      = fields.Text()

    @validation_rule
    def execution_and_node_exist(data):
        if not data.execution_id or not data.node_id:
            return # previous validation didn't pass

        from .models import Execution

        execution = Execution.get(data.execution_id)

        if execution is None:
            raise errors.InvalidFieldError(field='execution_id')

        from .process import load, iter_nodes, find
        from pvm_api import app

        name, xmlfile = load(app.config, execution.process_name)
        xmliter = iter_nodes(xmlfile)

        def testfunc(e):
            return 'id' in e.attrib and e.attrib['id'] == data.node_id

        try:
            find(xmliter, testfunc)
        except ElementNotFound:
            raise errors.InvalidFieldError(field='node_id')


def bind_forms(engine):
    ContinueProcess.set_engine(engine)
