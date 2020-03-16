from unittest.mock import MagicMock
import simplejson as json

from cacahuate.handler import Handler
from cacahuate.models import Execution, Pointer
from cacahuate.xml import Xml

from ..utils import make_pointer, make_user


def test_exit_interaction(config, mongo):
    handler = Handler(config)
    user = make_user('juan', 'Juan')
    ptr = make_pointer('exit.2018-05-03.xml', 'start_node')
    channel = MagicMock()
    execution = ptr.proxy.execution.get()

    mongo[config["EXECUTION_COLLECTION"]].insert_one({
        '_type': 'execution',
        'id': execution.id,
        'state': Xml.load(config, execution.process_name).get_state(),
    })

    # first node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': user.identifier,
        'input': [],
    }, channel)
    ptr = Pointer.get_all()[0]
    assert ptr.node_id

    args = channel.basic_publish.call_args[1]

    assert args['exchange'] == ''
    assert args['routing_key'] == config['RABBIT_QUEUE']
    assert json.loads(args['body']) == {
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }

    # exit node
    handler.call({
        'command': 'step',
        'pointer_id': ptr.id,
        'user_identifier': '__system__',
        'input': [],
    }, channel)

    assert len(Pointer.get_all()) == 0
    assert len(Execution.get_all()) == 0

    # state is coherent
    state = next(mongo[config["EXECUTION_COLLECTION"]].find({
        'id': execution.id,
    }))

    del state['_id']
    del state['finished_at']

    assert state == {
        '_type': 'execution',
        'id': execution.id,
        'name': '',
        'description': '',
        'state': {
            '_type': ':sorted_map',
            'items': {
                'start_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'start_node',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            'juan': {
                                '_type': 'actor',
                                'forms': [],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': 'juan',
                                    'fullname': 'Juan',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },

                'exit': {
                    '_type': 'node',
                    'type': 'exit',
                    'id': 'exit',
                    'state': 'valid',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {
                            '__system__': {
                                '_type': 'actor',
                                'forms': [],
                                'state': 'valid',
                                'user': {
                                    '_type': 'user',
                                    'identifier': '__system__',
                                    'fullname': 'System',
                                },
                            },
                        },
                    },
                    'milestone': False,
                    'name': 'Exit exit',
                    'description': 'Exit exit',
                },

                'final_node': {
                    '_type': 'node',
                    'type': 'action',
                    'id': 'final_node',
                    'state': 'unfilled',
                    'comment': '',
                    'actors': {
                        '_type': ':map',
                        'items': {},
                    },
                    'milestone': False,
                    'name': '',
                    'description': '',
                },
            },
            'item_order': ['start_node', 'exit', 'final_node'],
        },
        'status': 'finished',
        'actors': {
            'exit': '__system__',
            'start_node': 'juan',
        },
        'actor_list': [
            {
                'node': 'start_node',
                'identifier': 'juan',
            },
            {
                'node': 'exit',
                'identifier': '__system__',
            },
        ],
    }
