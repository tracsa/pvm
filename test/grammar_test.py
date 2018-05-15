from cacahuate.grammar import Condition
from cacahuate.models import Execution, Questionaire, Input


def test_condition():
    exc = Execution().save()

    form1 = Questionaire(ref='form1').save()
    form1.proxy.execution.set(exc)
    input1 = Input(name='answer', value='yes').save()
    input1.proxy.form.set(form1)

    form2 = Questionaire(ref='form2', data={'answer': 'no'}).save()
    form2.proxy.execution.set(exc)
    input2 = Input(name='answer', value='no').save()
    input2.proxy.form.set(form2)

    con = Condition(exc)

    assert con.parse('form1.answer=="yes"')
    assert not con.parse('form1.answer == "no"')
    assert con.parse('form2.answer =="no"')
