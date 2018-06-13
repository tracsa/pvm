expression: expression op expression
          | "(" expression ")"
          | ref
          | string
          | number

op: "==" -> op_eq
  | "!=" -> op_ne
  | "<" -> op_lt
  | "<=" -> op_lte
  | ">" -> op_gt
  | ">=" -> op_gte
  | "||" -> op_or
  | "&&" -> op_and

ref: variable "." variable

string : ESCAPED_STRING
variable: /[a-zA-Z_][a-zA-Z0-9_]*/
number: SIGNED_NUMBER

%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
