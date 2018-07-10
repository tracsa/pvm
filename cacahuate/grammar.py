from lark import Lark, Transformer
import operator
import os


class Condition:

    def __init__(self):
        filename = os.path.join(
            os.path.dirname(__file__),
            'grammars/condition.g'
        )

        with open(filename) as grammar_file:
            self.parser = Lark(
                grammar_file.read(),
                start='or_test',
                parser='lalr',
            )

    def parse(self, string):
        ''' returns the tree '''
        return self.parser.parse(string)


class ConditionTransformer(Transformer):
    ''' can be used to transform a tree like this:

    ConditionTransformer(values).transform(tree)

    where values is taken from the state of the execution '''

    def __init__(self, values):
        self._values = values

    def op_eq(self, _):
        return operator.eq

    def op_ne(self, _):
        return operator.ne

    def op_lt(self, _):
        return operator.lt

    def op_lte(self, _):
        return operator.le

    def op_gt(self, _):
        return operator.gt

    def op_gte(self, _):
        return operator.ge

    def op_or(self, _):
        return operator.or_

    def op_and(self, _):
        return operator.and_

    def op_not(self, _):
        return operator.not_

    def variable(self, tokens):
        # just copy the token as string
        return tokens[0][:]

    def obj_id(self, tokens):
        # copy the token as string
        return tokens[0][:]

    def ref(self, tokens):
        obj_id, member = tokens

        return self._values[obj_id][member]

    def string(self, tokens):
        return tokens[0][1:-1]

    def number(self, tokens):
        return float(tokens[0])

    def test_aux(self, tokens):
        if len(tokens) == 1:
            return tokens[0]
        if len(tokens) == 2:
            op, right = tokens
            return op(right)
        left, op, right = tokens
        return op(left, right)

    def or_test(self, tokens):
        return self.test_aux(tokens)

    def and_test(self, tokens):
        return self.test_aux(tokens)

    def not_test(self, tokens):
        return self.test_aux(tokens)

    def comparison(self, tokens):
        return self.test_aux(tokens)

    def atom_expr(self, tokens):
        return self.test_aux(tokens)
