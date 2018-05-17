condition: expr op expr

op: "==" -> op_eq
  | "!=" -> op_ne
  | "<" -> op_lt
  | "<=" -> op_lte
  | ">" -> op_gt
  | ">=" -> op_gte
  | "||" -> op_or
  | "&&" -> op_and

expr: ref
    | string

ref: obj_id "." member

obj_id: variable
member: variable

string : ESCAPED_STRING
variable: /[a-zA-Z0-9_-]+/

%import common.ESCAPED_STRING
%import common.WS
%ignore WS
