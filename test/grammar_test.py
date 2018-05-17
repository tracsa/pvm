import pytest

from cacahuate.grammar import Condition


def test_condition(config):
    state = {
        '_type': ':sorted_map',
        'items': {
            'first-node': {
                '_type': 'node',
                'id': 'first-node',
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {
                        'juan': {
                            '_type': 'actor',
                            'forms': [
                                {
                                    '_ref': 'first-form',
                                    '_type': 'form',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'item_order': [
                                            'param1',
                                        ],
                                        'items': {
                                            'param1': {
                                                'type': 'text',
                                                'value': 'value1'
                                            },
                                        },
                                    },
                                },
                            ],
                        },
                    },
                },
            },
            'second-node': {
                '_type': 'node',
                'id': 'second-node',
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {
                        'pedro': {
                            '_type': 'actor',
                            'forms': [
                                {
                                    '_ref': 'second-form',
                                    '_type': 'form',
                                    'inputs': {
                                        '_type': ':sorted_map',
                                        'item_order': [
                                            'param1',
                                            'param2',
                                        ],
                                        'items': {
                                            'param1': {
                                                'type': 'text',
                                                'value': 'value1'
                                            },
                                            'param2': {
                                                'type': 'text',
                                                'value': 'value2'
                                            },
                                        },
                                    },
                                },
                            ],
                        },
                    },
                },
            },
        },
        'item_order': [
            'first-node',
            'second-node',
        ],
    }

    con = Condition(state)

    assert con.parse('first-form.param1 == "value1"')
    assert con.parse('second-form.param1 == "value1"')
    assert con.parse('second-form.param2 == "value2"')

    assert con.parse('first-form.param1 != "nonsense"')
    assert not con.parse('first-form.param1 == "nonsense"')

    assert con.parse('first-form.param1 == second-form.param1')
    assert not con.parse('first-form.param1 == second-form.param2')
