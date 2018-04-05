from cacahuate.grammar import Condition
from cacahuate.models import Execution, Questionaire


def test_condition(models):
    exc = Execution().save()
    form1 = Questionaire(ref='#form1', data={'answer': 'yes'}).save()
    form2 = Questionaire(ref='#form2', data={'answer': 'no'}).save()
    form1.proxy.execution.set(exc)
    form2.proxy.execution.set(exc)

    con = Condition(exc)

    assert con.parse('form#form1[answer]=="yes"')
    assert not con.parse('form#form1[answer] == "no"')
    assert con.parse('form#form2[answer] =="no"')
