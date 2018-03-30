from pvm.grammar import Condition

def test_condition():
    con = Condition({
        'forms': [
            {
                'ref': '#form_id',
                'data': {
                    'input_name': 'yes',
                },
            },
        ],
    })

    assert con.parse("form#form_id.input_name==\"yes\"")
    assert not con.parse("form#form_id.input_name == \"no\"")
    assert con.parse("form#form_id.input_name ==\"yes\"")
