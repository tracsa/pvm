from lark import Lark, Transformer
import os


class Condition:

    def __init__(self, data):
        self.data = data

        filename = os.path.join(os.path.dirname(__file__), 'grammars/condition.ebnf')

        with open(filename) as grammar_file:
            self.parser = Lark(
                grammar_file.read(),
                start='condition',
                parser='lalr',
                transformer = self.ConditionTransformer(),
            )

    class ConditionTransformer(Transformer):
        def conditional(self, args):
            left, op, right = args

            if op == '==':
                return left == right
            elif op == '!=':
                return left != right

    def parse(self, string):
        return self.parser.parse(string)
