import pytest
from cacahuate.main import xml_validate


def test_condition():
    assert xml_validate('condition.2018-05-28.xml') is True


def test_id_repeat():
    with pytest.raises(SystemExit) as cm:
        xml_validate('condition_id_repeat.2018-05-28.xml')
    assert str(cm.value) == "Error id: 'condition1' "\
        "repeat in condition_id_repeat.2018-05-28.xml"


def test_not_param():
    with pytest.raises(SystemExit) as cm:
        xml_validate('condition_not_param.2018-05-28.xml')
    assert str(cm.value) == "Not param 'answesr' "\
        "in form#mistery in condition_not_param.2018-05-28.xml"


def test_not_dep():
    with pytest.raises(SystemExit) as cm:
        xml_validate('condition_not_dep.2018-05-28.xml')
    assert str(cm.value) == "Not dependence "\
        "'form#mistery.answerdd' in condition_not_dep.2018-05-28.xml"


def test_not_valid():
    with pytest.raises(SystemExit) as cm:
        xml_validate('condition_not_valid.2018-05-28.xml')
    assert str(cm.value) == 'Error mistery.answer == '\
        '"abrete sesamod" in  condition_not_valid.2018-05-28.xml'
