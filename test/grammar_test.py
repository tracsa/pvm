from pvm.grammar import Condition

def test_condition():
    con = Condition({
        'form_id': {
            'input_name': 'yes',
        },
    })

    assert con.parse("true==false") == False
    assert con.parse("true==true") == True
    assert con.parse("false==false") == True
    assert con.parse("false==true") == True

    # assert con.parse("#form_id.input_name=='yes'")
    # assert not con.parse('#form_id.input_name == no')
    # assert con.parse('#form_id.input_name ==yes')
