import pytest

from cacahuate.grammar import Condition


def state_generator(actions):
    state = {
        '_type': ':sorted_map',
        'items': {},
        'item_order': [],
    }

    for action in actions:
        node, actor, form_ref, input_name, value = action

        if node not in state['items']:
            state['items'][node] = {
                '_type': 'node',
                'id': node,
                'state': 'valid',
                'comment': '',
                'actors': {
                    '_type': ':map',
                    'items': {},
                },
            }

            state['item_order'].append(node)

        node = state['items'][node]

        if actor not in node['actors']['items']:
            node['actors']['items'][actor] = {
                '_type': 'actor',
                'forms': []
            }

        actor = node['actors']['items'][actor]

        form = {
            'ref': form_ref,
            '_type': 'form',
            'inputs': {
                '_type': ':sorted_map',
                'item_order': [
                    input_name,
                ],
                'items': {
                    input_name: {
                        'type': 'text',
                        'value': value,
                    },
                },
            },
        }

        actor['forms'].append(form)

    return state


def test_condition(config):
    state = state_generator([
        ('first-node', 'juan', 'first-form', 'param1', 'value1'),
        ('first-node', 'pedro', 'second-form', 'param1', 'value1'),
        ('first-node', 'pedro', 'second-form', 'param2', 'value2'),
    ])

    con = Condition(state)

    assert con.parse('first-form.param1 == "value1"')
    assert con.parse('second-form.param1 == "value1"')
    assert con.parse('second-form.param2 == "value2"')

    assert con.parse('first-form.param1 != "nonsense"')
    assert not con.parse('first-form.param1 == "nonsense"')

    assert con.parse('first-form.param1 == second-form.param1')
    assert not con.parse('first-form.param1 == second-form.param2')


def test_aritmetic_operators(config):
    state = state_generator([
        ('first-node', 'juan', 'set', 'A', '-1'),
        ('first-node', 'juan', 'set', 'B', '1'),
        ('first-node', 'juan', 'set', 'C', '1.0'),
        ('first-node', 'juan', 'set', 'D', '1.5'),
    ])

    con = Condition(state)

    assert con.parse('set.A < set.B')
    assert not con.parse('set.A > set.B')

    assert not con.parse('set.B < set.C')
    assert con.parse('set.B <= set.C')

    assert con.parse('set.C < set.D')


def test_logic_operators(config):
    state = state_generator([
        ('first-node', 'juan', 'set', 'A', 'true'),
        ('first-node', 'juan', 'set', 'B', ''),
    ])

    con = Condition(state)

    assert con.parse('set.A || set.B')
    assert not con.parse('set.A && set.B')
    assert not con.parse('set.A && set.B')
