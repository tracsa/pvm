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

    tree = Condition().parse('set.A AND set.B')
    assert ConditionTransformer(values).transform(tree) is False

    tree = Condition().parse('set.A OR set.B')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.A AND set.B OR set.A')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.B OR set.B OR set.A')
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse('set.A AND set.B AND set.A')
    assert ConditionTransformer(values).transform(tree) is False


def test_constants():
    tree = Condition().parse('TRUE')
    assert ConditionTransformer({}).transform(tree) is True

    tree = Condition().parse('FALSE')
    assert ConditionTransformer({}).transform(tree) is False


def test_no():
    values = {
        'set': {
            'A': True,
            'B': False,
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


def test_list():
    tree = Condition().parse('[]')
    assert ConditionTransformer({}).transform(tree) == []

    tree = Condition().parse('["hello",]')
    assert ConditionTransformer({}).transform(tree) == ['hello']

    tree = Condition().parse('[0,]')
    assert ConditionTransformer({}).transform(tree) == [0]

    tree = Condition().parse('[1, 2, 3]')
    assert ConditionTransformer({}).transform(tree) == [1, 2, 3]

    tree = Condition().parse('3 IN [1, 2, 3]')
    assert ConditionTransformer({}).transform(tree) == True

    tree = Condition().parse('4 NOT IN [1, 2, 3]')
    assert ConditionTransformer({}).transform(tree) == True

    tree = Condition().parse('4 IN [1, 2, 3]')
    assert ConditionTransformer({}).transform(tree) == False

    tree = Condition().parse('[1, 2, 3] == [1, 2, 3,]')
    assert ConditionTransformer({}).transform(tree) == True


def test_everything():
    values = {
        'form': {
            'input': "no",
        },
    }

    tree = Condition().parse(
        '!!3<0 || !(form.input == "0" && ("da" != "de"))'
    )
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse(
        '!!3<0 OR !(form.input == "0" AND ("da" != "de"))'
    )
    assert ConditionTransformer(values).transform(tree) is True

    tree = Condition().parse(
        'FALSE OR !(form.input == "0" AND TRUE)'
    )
    assert ConditionTransformer(values).transform(tree) is True
