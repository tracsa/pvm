import pytest
from cacahuate.main import xml_validate


def test_xml_validates():
    assert xml_validate('xml/simple.2018-02-19.xml') is None


def test_id_repeat():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_id_repeat.2018-05-28.xml')
    assert str(cm.value) == \
        "xml/condition_id_repeat.2018-05-28.xml: Duplicated id: 'start-node'"


def test_not_param():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_param.2018-05-28.xml')
    assert str(cm.value) == \
        "xml/condition_not_param.2018-05-28.xml: Referenced param does not " \
        "exist 'a.b'"


def test_not_dep():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_dep.2018-05-28.xml')
    assert str(cm.value) == \
        "xml/condition_not_dep.2018-05-28.xml: Referenced dependency does " \
        "not exist 'a.b'"


def test_not_valid():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_valid.2018-05-28.xml')
    assert str(cm.value) == \
        'xml/condition_not_valid.2018-05-28.xml: Lex error in condition'
