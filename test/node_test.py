from cacahuate.xml import Xml
from cacahuate.node import make_node


def test_resolve_params(config):
    xml = Xml.load(config, 'exit_request')
    xmliter = iter(xml)
    next(xmliter)
    node = make_node(next(xmliter))

    state = {
        'state': {
            'items': {
                'requester': {
                    'actors': {
                        'items': {
                            'juan': {
                                'user': {
                                    'identifier': 'juan',
                                },
                                'forms': [{
                                    'inputs': {
                                        'items': {
                                            'reason': {
                                                'value': 'nones',
                                            },
                                        },
                                    },
                                }],
                            },
                        },
                    },
                },
            },
        },
    }

    assert node.resolve_params(state) == {
        "identifier": 'juan',
        "relation": 'manager',
        "reason": 'nones',
    }
