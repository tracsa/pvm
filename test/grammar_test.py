import pytest

from cacahuate.grammar import Condition


def test_condition(config):
    con = Condition({
        'first-form': {
            'param1': 'value1',
        },
        'second-form': {
            'param1': 'value1',
            'param2': 'value2',
        },
    })

    assert con.parse('first-form.param1 == "value1"')
    assert con.parse('second-form.param1 == "value1"')
    assert con.parse('second-form.param2 == "value2"')

    assert con.parse('first-form.param1 != "nonsense"')
    assert not con.parse('first-form.param1 == "nonsense"')

    assert con.parse('first-form.param1 == second-form.param1')
    assert not con.parse('first-form.param1 == second-form.param2')


def test_aritmetic_operators(config):
    con = Condition({
        'set': {
            'A': '-1',
            'B': '1',
            'C': '1.0',
            'D': '1.5',
        },
    })

    assert con.parse('set.A < set.B')
    assert not con.parse('set.A > set.B')

    assert not con.parse('set.B < set.C')
    assert con.parse('set.B <= set.C')

    assert con.parse('set.C < set.D')


def test_logic_operators(config):
    con = Condition({
        'set': {
            'A': 'true',
            'B': '',
        },
    })

    assert con.parse('set.A || set.B')
    assert not con.parse('set.A && set.B')
    assert not con.parse('set.A && set.B')
