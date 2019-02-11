// reference from: https://docs.python.org/3/reference/grammar.html

or_test: and_test (op_or and_test)*

and_test: not_test (op_and not_test)*

not_test: op_not not_test
        | comparison

comparison: atom_expr (comp_op atom_expr)*

atom_expr: "(" or_test ")"
         | string
         | ref
         | number

ref: variable "." variable

// common operators

op_or: "||" -> op_or
     | "OR" -> op_or

op_and: "&&" -> op_and
      | "AND" -> op_and

op_not: "!" -> op_not

comp_op: "==" -> op_eq
       | "!=" -> op_ne
       | "<" -> op_lt
       | "<=" -> op_lte
       | ">" -> op_gt
       | ">=" -> op_gte

// common atoms

string : ESCAPED_STRING
variable: /[a-zA-Z_][a-zA-Z0-9_]*/
number: SIGNED_NUMBER

%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
