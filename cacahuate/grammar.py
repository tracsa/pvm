from lark import Lark, Transformer
import operator
import os

from cacahuate.errors import RefNotFound


class Condition:

    def __init__(self, execution):
        filename = os.path.join(
                                os.path.dirname(__file__),
                                'grammars/condition.g'
                                )

        with open(filename) as grammar_file:
            self.parser = Lark(
                grammar_file.read(),
                start='condition',
                parser='lalr',
                transformer=self.ConditionTransformer(execution),
            )

    def parse(self, string):
        return self.parser.parse(string)

    class ConditionTransformer(Transformer):

        def __init__(self, execution):
            self._execution = execution

        def op_eq(self, _):
            return operator.eq

        def op_ne(self, _):
            return operator.ne

        def variable(self, args):
            return args[0][:]

        def obj_id(self, args):
            return args[0][:]

        def member(self, args):
            return args[0][:]

        def ref(self, args):
            obj_id, member = args

            try:
                obj = next(self._execution.proxy.forms.q().filter(ref=obj_id))
            except StopIteration:
                raise RefNotFound

            return obj.data.get(member)

        def string(self, args):
            return args[0][1:-1]

        def condition(self, args):
            left, op, right = args

            return op(left, right)
