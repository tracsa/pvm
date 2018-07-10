from cacahuate.grammar import Condition, ConditionTransformer


def test_condition():
    values = {
        'first_form': {
            'param1': 'value1',
        },
        'second_form': {
            'param1': 'value1',
            'param2': 'value2',
        },
    }

    tree = Condition().parse('first_form.param1 == "value1"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('second_form.param1 == "value1"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('second_form.param2 == "value2"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first_form.param1 != "nonsense"')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first_form.param1 == "nonsense"')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('first_form.param1 == second_form.param1')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('first_form.param1 == second_form.param2')
    assert ConditionTransformer(values).transform(tree) is False


def test_aritmetic_operators():
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


def test_logic_operators():
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

def test_no():
    values = {
        'set': {
            'A' : True,
            'B' : False,
        },
    }

    tree = Condition().parse('!set.A')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('set.A && !set.B')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('!set.A && set.B')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('!!0>-2')
    assert ConditionTransformer(values).transform(tree) is True

def test_everything():
    values = {
        'form': {
            'input': "no",
        },
    }

    tree = Condition().parse('!!3<0 || !(form.input == "0" && ("da" != "de"))')
    assert ConditionTransformer(values).transform(tree) is True
