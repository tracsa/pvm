import pytest
from cacahuate.xml_validate import main


def test_condition():
    assert main('condition.2018-05-28.xml') is True


def test_id_repeat():
    with pytest.raises(SystemExit) as cm:
        main('condition_id_repeat.2018-05-28.xml')
    assert str(cm.value) == "Error id: 'condition1' "\
        "repeat in condition_id_repeat.2018-05-28.xml"


def test_not_param():
    with pytest.raises(SystemExit) as cm:
        main('condition_not_param.2018-05-28.xml')
    assert str(cm.value) == "Not param 'answesr' "\
        "in form#mistery in condition_not_param.2018-05-28.xml"


def test_not_dep():
    with pytest.raises(SystemExit) as cm:
        main('condition_not_dep.2018-05-28.xml')
    assert str(cm.value) == "Not dependence "\
        "'form#mistery.answerdd' in condition_not_dep.2018-05-28.xml"


def test_not_valid():
    with pytest.raises(SystemExit) as cm:
        main('condition_not_valid.2018-05-28.xml')
    assert str(cm.value) == 'Error mistery.answer == '\
        '"abrete sesamod" in  condition_not_valid.2018-05-28.xml'
