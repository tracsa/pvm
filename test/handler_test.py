from datetime import datetime
from unittest.mock import MagicMock
from xml.dom.minidom import Document
import pika
import pytest
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer, User, Questionaire, \
    Activity, Input
from cacahuate.node import Action

from .utils import make_pointer, make_activity, make_user


def test_recover_step(config):
    handler = Handler(config)
    ptr = make_pointer('simple.2018-02-19.xml', 'mid-node')
    exc = ptr.proxy.execution.get()
    manager = make_user('juan_manager', 'Manager')

    pointer, user, input = \
        handler.recover_step({
            'command': 'step',
            'pointer_id': ptr.id,
            'user_identifier': 'juan_manager',
            'input': [[
                'auth-form',
                [{
                    'auth': 'yes',
                }],
            ]],
        })

    assert pointer.id == pointer.id
    assert user.id == manager.id


def test_create_pointer(config):
    handler = Handler(config)

    ele = Document().createElement('node')
    ele.setAttribute('class', 'simple')
    ele.setAttribute('id', 'chubaca')

    node_name = Document().createTextNode('nombre')
    node_desc = Document().createTextNode('descripción')

    # Build node structure
    node_info_el = Document().createElement('node-info')
    node_name_el = Document().createElement('name')
    node_desc_el = Document().createElement('description')

    node_name_el.appendChild(node_name)
    node_info_el.appendChild(node_name_el)

    node_desc_el.appendChild(node_desc)
    node_info_el.appendChild(node_desc_el)

    ele.appendChild(node_info_el)

    node = Action(ele)
    exc = Execution.validate(
        process_name='simple.2018-02-19.xml',
        name='nombre',
        description='description'
    ).save()
    pointer = handler.create_pointer(node, exc)
    execution = pointer.proxy.execution.get()

    assert pointer.node_id == 'chubaca'

    assert execution.process_name == 'simple.2018-02-19.xml'
    assert execution.proxy.pointers.count() == 1


def test_wakeup(config, mongo):
    ''' the first stage in a node's lifecycle '''
    # setup stuff
    handler = Handler(config)

    pointer = make_pointer('simple.2018-02-19.xml', 'start-node')
    execution = pointer.proxy.execution.get()
    juan = User(identifier='juan').save()
    manager = User(identifier='juan_manager').save()
    act = make_activity('start-node', juan, execution)
    ques = Questionaire(ref='start-form', data={'data': 'why not'}).save()
    ques.proxy.execution.set(execution)

    channel = MagicMock()

    # this is what we test
    handler.call({
        'command': 'step',
        'pointer_id': pointer.id,
        'user_identifier': '',
        'input': [],
    }, channel)

    # test manager is notified
    channel.basic_publish.assert_called_once()
    channel.exchange_declare.assert_called_once()

    args = channel.basic_publish.call_args[1]

    assert args['exchange'] == config['RABBIT_NOTIFY_EXCHANGE']
    assert args['routing_key'] == 'email'
    assert json.loads(args['body']) == {
        'email': 'hardcoded@mailinator.com',
        'pointer': Pointer.get_all()[0].to_json(include=['*', 'execution']),
    }

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert (reg['started_at'] - datetime.now()).total_seconds() < 2
    assert reg['finished_at'] is None
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == 'mid-node'
    assert reg['actors'] == []
    assert reg['notified_users'] == [manager.to_json()]
    with pytest.raises(KeyError):
        reg['state']

    # tasks where asigned
    assert manager.proxy.tasks.count() == 1

    task = manager.proxy.tasks.get()[0]

    assert isinstance(task, Pointer)
    assert task.node_id == 'mid-node'
    assert task.proxy.execution.get().id == execution.id


def test_teardown(config, mongo):
    ''' second and last stage of a node's lifecycle '''
    # test setup
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'mid-node')
    execution = p_0.proxy.execution.get()

    juan = User(identifier='juan').save()
    manager = User(identifier='manager').save()
    manager2 = User(identifier='manager2').save()

    manager.proxy.tasks.set([p_0])
    manager2.proxy.tasks.set([p_0])

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': p_0.node_id,
        },
        'actors': [],
    })

    channel = MagicMock()

    # the thing to test
    handler.call({
        'command': 'step',
        'pointer_id': p_0.id,
        'user_identifier': manager.identifier,
        'input': [[
            'mid-form',
            [{
                'name': 'data',
                'value': 'yes',
                'type': 'text',
            }],
        ]],
    }, channel)

    # assertions
    assert Pointer.get(p_0.id) is None

    assert Pointer.count() == 1
    assert Pointer.get_all()[0].node_id == 'final-node'

    # mongo has a registry
    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == execution.id
    assert reg['node']['id'] == p_0.node_id
    assert reg['actors'] == [{
        'ref': 'mid-node',
        'user': {
            'identifier': 'manager',
            'human_name': None,
        },
        'forms': [{
            'ref': 'mid-form',
            'inputs': [{
                'type': 'text',
                'name': 'data',
                'value': 'yes',
            }],
        }],
    }]
    with pytest.raises(KeyError):
        reg['state']

    # tasks where deleted from user
    assert manager.proxy.tasks.count() == 0
    assert manager2.proxy.tasks.count() == 0

    # activity is created
    activities = execution.proxy.actors.get()

    assert len(activities) == 1
    assert activities[0].ref == 'mid-node'
    assert activities[0].proxy.user.get() == manager

    # form is attached
    forms = execution.proxy.forms.get()

    assert len(forms) == 1
    assert forms[0].ref == 'mid-form'
    assert forms[0] in activities[0].proxy.forms

    # input is attached to form
    inputs = Input.get_all()

    assert len(inputs) == 1
    assert inputs[0].name == 'data'
    assert inputs[0].type == 'text'
    assert inputs[0].value == 'yes'
    assert inputs[0] in forms[0].proxy.inputs


def test_finish_execution(config, mongo):
    handler = Handler(config)

    p_0 = make_pointer('simple.2018-02-19.xml', 'manager')
    execution = p_0.proxy.execution.get()
    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'status': 'ongoing',
        'id': execution.id
    })

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())
    assert execution.id == reg['id']

    handler.finish_execution(execution)

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg['status'] == 'finished'
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2


def test_call_handler_delete_process(config, mongo):
    handler = Handler(config)
    channel = MagicMock()
    method = {'delivery_tag': True}
    properties = ""
    pointer = make_pointer('simple.2018-02-19.xml', 'requester')
    execution_id = pointer.proxy.execution.get().id
    body = '{"command":"cancel", "execution_id":"%s", "pointer_id":"%s"}'\
        % (execution_id, pointer.id)

    mongo[config["MONGO_EXECUTION_COLLECTION"]].insert_one({
            'started_at': datetime(2018, 4, 1, 21, 45),
            'finished_at': None,
            'status': 'ongoing',
            'id': execution_id
        })

    handler(channel, method, properties, body)

    reg = next(mongo[config["MONGO_EXECUTION_COLLECTION"]].find())

    assert reg['id'] == execution_id
    assert reg['status'] == "cancelled"
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2

    assert Execution.count() == 0
    assert Pointer.count() == 0
    assert Questionaire.count() == 0
    assert Activity.count() == 0


def test_approve(config, mongo):
    ''' tests that a validation node can go forward on approval '''
    # test setup
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('validation.2018-05-09.xml', 'approval-node')
    channel = MagicMock()

    mongo[config["MONGO_HISTORY_COLLECTION"]].insert_one({
        'started_at': datetime(2018, 4, 1, 21, 45),
        'finished_at': None,
        'execution': {
            'id': execution.id,
        },
        'node': {
            'id': p_0.node_id,
        },
        'actors': [],
    })

    # thing to test
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': {
            'response': 'accept',
            'comment': 'I like it',
        },
    }, channel)

    # assertions
    assert Pointer.get(ptr.id) is None

    new_ptr = Pointer.get_all()[0]
    assert new_ptr.node_id == 'final-node'

    reg = next(mongo[config["MONGO_HISTORY_COLLECTION"]].find())

    assert reg['started_at'] == datetime(2018, 4, 1, 21, 45)
    assert (reg['finished_at'] - datetime.now()).total_seconds() < 2
    assert reg['execution']['id'] == ptr.execution
    assert reg['node']['id'] == 'approval-node'
    assert reg['actors'] == [{
        'ref': 'mid-node',
        'user': {
            'identifier': 'manager',
            'human_name': None,
        },
        'node': {
            'type': 'validation',
        },
        'input': {
            'response': 'accept',
            'comment': 'I like it',
        },
    }]


def test_reject():
    ''' tests that a rejection moves the pointer to a backward position '''
    assert False


def test_rejected_doesnt_repeat():
    ''' asserts that a pointer moved to the past doesn't repeat a task that
    wasn't invalidated by the rejection '''
    assert False


def test_rejected_repeats():
    ''' asserts that a pointer moved to the past repeats the nodes that were
    invalidated '''
    assert False


@pytest.mark.skip
def test_patch():
    ''' ensure that a patch request moves the pointer accordingly '''
    assert False


def test_resistance_unexisteng_hierarchy_backend(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'noprov'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_hierarchy_return(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'return'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_hierarchy_item(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'item'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_node_not_found(config):
    handler = Handler(config)

    ptr = make_pointer('wrong.2018-04-11.xml', 'start-node')
    exc = ptr.proxy.execution.get()
    que = Questionaire(ref='form', data={'choice': 'nonode'}).save()
    que.proxy.execution.set(exc)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))


def test_resistance_dead_pointer(config):
    handler = Handler(config)

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': 'nones',
    }))


def test_resistance_dead_execution(config):
    handler = Handler(config)

    ptr = Pointer().save()

    # this is what we test
    handler(MagicMock(), MagicMock(), None, json.dumps({
        'command': 'step',
        'pointer_id': ptr.id,
    }))
