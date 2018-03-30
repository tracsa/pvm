from lark import Lark, Transformer
import operator
import os


class Condition:

    def __init__(self, data):
        self.data = data

        filename = os.path.join(os.path.dirname(__file__), 'grammars/condition.ebnf')

        with open(filename) as grammar_file:
            self.parser = Lark(
                grammar_file.read(),
                start = 'condition',
                parser = 'lalr',
                transformer = self.ConditionTransformer(),
            )

    def parse(self, string):
        return self.parser.parse(string)

    class ConditionTransformer(Transformer):
        op_eq = lambda self, _: operator.eq
        op_ne = lambda self, _: operator.ne

        true = lambda self, _: True
        false = lambda self, _: False

        def condition(self, args):
            left, op, right = args

            return op(left, right)
