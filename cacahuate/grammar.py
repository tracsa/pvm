from lark import Lark, Transformer
import operator
import os

from cacahuate.errors import RefNotFound


class Condition:

    def __init__(self, state):
        filename = os.path.join(
            os.path.dirname(__file__),
            'grammars/condition.g'
        )

        with open(filename) as grammar_file:
            self.parser = Lark(
                grammar_file.read(),
                start='condition',
                parser='lalr',
                transformer=self.ConditionTransformer(state),
            )

    def parse(self, string):
        return self.parser.parse(string)

    class ConditionTransformer(Transformer):

        def __init__(self, state):
            self._state = state

        def op_eq(self, _):
            return operator.eq

        def op_ne(self, _):
            return operator.ne

        def op_lt(self, _):
            def lt(a, b):
                a = float(next(a.scan_values(lambda x: True)))
                b = float(next(b.scan_values(lambda x: True)))
                return a < b

            return lt

        def op_lte(self, _):
            def lte(a, b):
                a = float(next(a.scan_values(lambda x: True)))
                b = float(next(b.scan_values(lambda x: True)))
                return a <= b

            return lte

        def op_gt(self, _):
            def gt(a, b):
                a = float(next(a.scan_values(lambda x: True)))
                b = float(next(b.scan_values(lambda x: True)))
                return a > b

            return gt

        def op_gte(self, _):
            def gte(a, b):
                a = float(next(a.scan_values(lambda x: True)))
                b = float(next(b.scan_values(lambda x: True)))
                return a >= b

            return gte

        def op_or(self, _):
            def operator_or(a, b):
                a = next(a.scan_values(lambda x: True))
                b = next(b.scan_values(lambda x: True))
                return a or b

            return operator_or

        def op_and(self, _):
            def operator_and(a, b):
                a = next(a.scan_values(lambda x: True))
                b = next(b.scan_values(lambda x: True))
                return a and b

            return operator_and

        def variable(self, args):
            return args[0][:]

        def obj_id(self, args):
            return args[0][:]

        def member(self, args):
            return args[0][:]

        def ref(self, args):
            obj_id, member = args

            # TODO there is an implementation of this in O(log N + K)
            for node in self._state['items'].values():
                actors = node['actors']
                for actor in actors['items'].values():
                    forms = actor['forms']
                    for form in forms:
                        if form['ref'] != obj_id:
                            continue

                        inputs = form['inputs']
                        if member in inputs['items']:
                            input = inputs['items'][member]

                            ret = None
                            if 'value' in input:
                                ret = input['value']

                            return ret

        def string(self, args):
            return args[0][1:-1]

        def condition(self, args):
            left, op, right = args

            return op(left, right)
