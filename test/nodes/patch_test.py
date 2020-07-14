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
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        },
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            Form.state_json('exit_form', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'want to pee',
                    'value_caption': 'want to pee',
                    'name': 'reason',
                },
            ]),
            Form.state_json('code_form', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'kadabra',
                    'value_caption': 'kadabra',
                    'name': 'code',
                },
            ]),
        ],
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
        'user_identifier': user.identifier,
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

    execution = mongo[config["EXECUTION_COLLECTION"]].find_one({
        'id': execution.id,
    })

    expected_values = {
        '_execution': [{
            'name': '',
            'description': '',
        }],
        'auth_form': [{'auth': 'yes'}],
        'code_form': [{'code': 'kadabra'}],
        'exit_form': [{'reason': 'want to pee'}],
    }
    assert execution['values'] == expected_values


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
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        },
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            Form.state_json('code_form', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'kadabra',
                    'value_caption': 'kadabra',
                    'name': 'code',
                },
            ]),
            Form.state_json('exit_form', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'want to pee',
                    'value_caption': 'want to pee',
                    'name': 'reason',
                },
            ]),
        ],
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
        'user_identifier': user.identifier,
        'comment': 'pee is not a valid reason',
        'inputs': [
            {
                'ref': 'requester.juan.1:exit_form.reason',
                'value': 'am hungry',
                'value_caption': 'am hungry',
            },
            {
                'ref': 'requester.juan.0:code_form.code',
                'value': 'alakazam',
                'value_caption': 'alakazam',
            },
        ],
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

    _input_0 = actor['forms'][0]['inputs']['items']['code']

    assert _input_0['value'] == 'alakazam'
    assert _input_0['value_caption'] == 'alakazam'

    _input_1 = actor['forms'][1]['inputs']['items']['reason']

    assert _input_1['value'] == 'am hungry'
    assert _input_1['value_caption'] == 'am hungry'

    execution = mongo[config["EXECUTION_COLLECTION"]].find_one({
        'id': execution.id,
    })

    expected_values = {
        '_execution': [{
            'name': '',
            'description': '',
        }],
        'auth_form': [{'auth': 'yes'}],
        'code_form': [{'code': 'alakazam'}],
        'exit_form': [{'reason': 'am hungry'}],
    }
    assert execution['values'] == expected_values


def test_patch_set_value_multiple(config, mongo):
    ''' patch and set new data (multiple)'''
    handler = Handler(config)
    user = make_user('kysxd', 'KYSXD')
    ptr = make_pointer('gift-request.2020-04-05.xml', 'solicitud')
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, 'gift-request').get_state(),
        'values': {
            '_execution': [{
                'name': '',
                'description': '',
            }],
        }
    })

    # requester fills the form
    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [
            Form.state_json('viaticos', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'yes',
                    'value_caption': 'Si',
                    'name': 'galletas',
                },
            ]),
            Form.state_json('condicionales', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'bueno',
                    'value_caption': 'Si',
                    'name': 'comportamiento',
                },
            ]),
            Form.state_json('regalos', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'Max Iron',
                    'value_caption': 'Max Iron',
                    'name': 'regalo',
                },
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 350.0,
                    'value_caption': 350.0,
                    'name': 'costo',
                },
            ]),
            Form.state_json('regalos', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'Mega boy',
                    'value_caption': 'Mega boy',
                    'name': 'regalo',
                },
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 120.0,
                    'value_caption': 120.0,
                    'name': 'costo',
                },
            ]),
            Form.state_json('regalos', [
                {
                    '_type': 'field',
                    'state': 'valid',
                    'value': 'Brobocop',
                    'value_caption': 'Brobocop',
                    'name': 'regalo',
                },
            ]),
        ],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]
    assert ptr.node_id == 'if_malo'

    channel = MagicMock()
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [Form.state_json('if_malo', [
            {
                'name': 'condition',
                'state': 'valid',
                'type': 'bool',
                'value': False,
                'value_caption': 'False',
            },
        ])],
    }, channel)
    auth_ptr = execution.proxy.pointers.get()[0]
    assert auth_ptr.node_id == 'preparacion'

    # patch request happens
    channel = MagicMock()
    handler.patch({
        'command': 'patch',
        'execution_id': execution.id,
        'user_identifier': user.identifier,
        'comment': 'Informacion equivocada',
        'inputs': [
            {
                'ref': 'solicitud.kysxd.3:regalos.regalo',
                'value': 'Mega bro',
                'value_caption': 'Mega bro',
            },
            {
                'ref': 'solicitud.kysxd.2:regalos.regalo',
                'value': 'Action bro',
                'value_caption': 'Action bro',
            },
            {
                'ref': 'solicitud.kysxd.5:regalos.costo',
                'value': 350.0,
                'value_caption': 350.0,
            },
            {
                'ref': 'solicitud.kysxd.2:regalos.costo',
                'value': 10.0,
                'value_caption': 10.0,
            },
        ],
    }, channel)
    ptr = execution.proxy.pointers.get()[0]

    assert ptr.node_id == 'if_malo'

    # nodes with pointers are marked as unfilled or invalid in execution state
    e_state = mongo[config['EXECUTION_COLLECTION']].find_one({
        'id': execution.id,
    })

    # values sent are set
    actor = e_state['state']['items']['solicitud']['actors']['items']['kysxd']

    # sanity check for the non-multiple forms
    _form = actor['forms'][0]
    _input = _form['inputs']['items']['galletas']
    assert _input['value'] == 'yes'
    assert _input['value_caption'] == 'Si'

    _form = actor['forms'][1]
    _input = _form['inputs']['items']['comportamiento']
    assert _input['value'] == 'bueno'
    assert _input['value_caption'] == 'Si'

    # check multiforms
    # first
    _form = actor['forms'][2]
    _input = _form['inputs']['items']['regalo']
    assert _input['value'] == 'Action bro'
    assert _input['value_caption'] == 'Action bro'

    _form = actor['forms'][2]
    _input = _form['inputs']['items']['costo']
    assert _input['value'] == 10.0
    assert _input['value_caption'] == 10.0

    # second
    _form = actor['forms'][3]
    _input = _form['inputs']['items']['regalo']
    assert _input['value'] == 'Mega bro'
    assert _input['value_caption'] == 'Mega bro'

    _form = actor['forms'][3]
    _input = _form['inputs']['items']['costo']
    assert _input['value'] == 120.0
    assert _input['value_caption'] == 120.0

    # third
    _form = actor['forms'][4]
    _input = _form['inputs']['items']['regalo']
    assert _input['value'] == 'Brobocop'
    assert _input['value_caption'] == 'Brobocop'

    # unexistant key doesn't update
    assert 'costo' not in _form['inputs']['items']

    expected_values = {
        '_execution': [{
            'name': '',
            'description': '',
        }],
        'viaticos': [{'galletas': 'yes'}],
        'condicionales': [{'comportamiento': 'bueno'}],
        'if_malo': [{'condition': False}],
        'regalos': [
            {'regalo': 'Action bro', 'costo': 10.0},
            {'regalo': 'Mega bro', 'costo': 120.0},
            {'regalo': 'Brobocop'},
        ],
    }
    assert e_state['values'] == expected_values
