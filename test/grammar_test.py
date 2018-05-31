import pytest

from cacahuate.grammar import Condition, ConditionTransformer


def test_condition(config):
    values = {
        'first-form': {
            'param1': 'value1',
        },
        'second-form': {
            'param1': 'value1',
            'param2': 'value2',
        },
    }

    tree = Condition().parse('first-form.param1 == "value1"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('second-form.param1 == "value1"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('second-form.param2 == "value2"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first-form.param1 != "nonsense"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first-form.param1 == "nonsense"')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('first-form.param1 == second-form.param1')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first-form.param1 == second-form.param2')
    assert ConditionTransformer(values).transform(tree) is False


def test_aritmetic_operators(config):
    values = {
        'set': {
            'A': -1,
            'B': 1,
            'C': 1.0,
            'D': 1.5,
        },
    }

    tree = Condition().parse('set.A < set.B')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.A > set.B')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('set.B < set.C')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('set.B <= set.C')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.C < set.D')
    assert ConditionTransformer(values).transform(tree) is True


def test_logic_operators(config):
    values = {
        'set': {
            'A': True,
            'B': False,
        },
    }

    tree = Condition().parse('set.A || set.B')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.A && set.B')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('set.A && set.B')
    assert ConditionTransformer(values).transform(tree) is False
