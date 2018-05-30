import pytest
from cacahuate.main import xml_validate


def test_condition():
    assert xml_validate('xml/condition.2018-05-28.xml') is True


def test_id_repeat():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_id_repeat.2018-05-28.xml')
    assert str(cm.value) == "Duplicated id: 'condition1'"


def test_not_param():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_param.2018-05-28.xml')
    assert str(cm.value) == \
        "Referenced param does not exist 'mistery.answesr'"


def test_not_dep():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_dep.2018-05-28.xml')
    assert str(cm.value) == \
        "Referenced dependency does not exist 'mistery.answerdd'"


def test_not_valid():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_valid.2018-05-28.xml')
    assert str(cm.value) == 'Lex error in condition'
