from unittest.mock import MagicMock

from cacahuate.handler import Handler
from cacahuate.node import Form
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user


def test_patch_invalidate(config, mongo):
    ''' patch that only invalidates '''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'exit_request').get_state(),
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('exit_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'want to pee',
                'value_caption': 'want to pee',
                'name': 'reason',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'manager'

    # manager says yes
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('auth_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'yes',
                'value_caption': 'yes',
                'name': 'auth',
            },
        ])],
    }, channel)
    security_ptr = execution.proxy.pointers.get()[0]
    assert security_ptr.node_id == 'security'

    # patch request happens
    channel = MagicMock()
    handler.patch({
        'command': 'patch',
        'execution_id': execution.id,
        'comment': 'pee is not a valid reason',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
        }],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]

    # pointer is in the first node
    assert ptr.node_id == 'requester'

    # nodes with pointers are marked as unfilled or invalid in execution state
    exc_state = mongo[config['EXECUTION_COLLECTION']].find_one({
        'id': execution.id,
    })

    assert exc_state['state']['items']['security']['state'] == 'unfilled'

    # dependent information is invalidated
    assert exc_state['state']['items']['manager']['state'] == 'invalid'

    # entries in pointer collection get a state of cancelled by patch request
    security_pointer_state = mongo[config['POINTER_COLLECTION']].find_one({
        'id': security_ptr.id,
    })

    assert security_pointer_state['state'] == 'cancelled'


def test_patch_set_value(config, mongo):
    ''' patch and set new data '''
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit_request.2018-03-20.xml', 'requester')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'exit_request').get_state(),
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('exit_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'want to pee',
                'value_caption': 'want to pee',
                'name': 'reason',
            },
        ])],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'manager'

    # manager says yes
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('auth_form', [
            {
                '_type': 'field',
                'state': 'valid',
                'value': 'yes',
                'value_caption': 'yes',
                'name': 'auth',
            },
        ])],
    }, channel)
    security_ptr = execution.proxy.pointers.get()[0]
    assert security_ptr.node_id == 'security'

    # patch request happens
    channel = MagicMock()
    handler.patch({
        'command': 'patch',
        'execution_id': execution.id,
        'comment': 'pee is not a valid reason',
        'inputs': [{
            'ref': 'requester.juan.0:exit_form.reason',
            'value': 'am hungry',
            'value_caption': 'am hungry',
        }],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]

    # pointer is in the manager's node
    assert ptr.node_id == 'manager'

    # nodes with pointers are marked as unfilled or invalid in execution state
    exc_state = mongo[config['EXECUTION_COLLECTION']].find_one({
        'id': execution.id,
    })

    # values sent are set
    actor = exc_state['state']['items']['requester']['actors']['items']['juan']
    _input = actor['forms'][0]['inputs']['items']['reason']

    assert _input['value'] == 'am hungry'
    assert _input['value_caption'] == 'am hungry'
