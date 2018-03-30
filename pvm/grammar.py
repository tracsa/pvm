from lark import Lark, Transformer
import operator
import os


class Condition:

    def __init__(self, data):
        self.data = data

        filename = os.path.join(os.path.dirname(__file__), 'grammars/condition.g')

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

        type_form = lambda self, _: 'form'

        def ref(self, args):
            obj_type, obj_id, member = args
            print(obj_id)

        def string(self, args):
            return args[0][1:-1]

        def condition(self, args):
            left, op, right = args

            return op(left, right)
