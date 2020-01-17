from unittest.mock import MagicMock

from cacahuate.handler import Handler
from cacahuate.models import Pointer
from cacahuate.xml import Xml
from cacahuate.node import Form

from .utils import make_pointer, make_user


def test_variable_proc_name(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('variable_name.2020-01-17.xml', 'start_node')
    execution = ptr.proxy.execution.get()
    channel = MagicMock()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
    })

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form01', [
            {
                'name': 'data01',
                'type': 'text',
                'value': '1',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node02'

    # name changed
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    assert execution.name == 'Variable name process in step 1'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form02', [
            {
                'name': 'data02',
                'type': 'text',
                'value': '2',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    ptr = Pointer.get_all()[0]
    assert ptr.node_id == 'node03'

    # name changed
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    assert execution.name == 'Variable name process in step 2'

    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('form03', [
            {
                'name': 'data03',
                'type': 'text',
                'value': '3',
            },
        ])],
    }, channel)

    # pointer moved
    assert Pointer.get(ptr.id) is None
    len(Pointer.get_all()) == 0

    # name changed
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    assert execution.name == 'Variable name process in step 3'
