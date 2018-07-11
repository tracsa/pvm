import pytest
from cacahuate.main import xml_validate


def test_xml_validation():
    assert xml_validate('xml/simple.2018-02-19.xml') is None


def test_xml_validation_repeated_id():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_id_repeat.2018-05-28.xml')

    assert str(cm.value) == \
        "xml/condition_id_repeat.2018-05-28.xml: Duplicated id: 'start_node'"


def test_xml_validation_unexistent_param():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_param.2018-05-28.xml')

    assert str(cm.value) == \
        "xml/condition_not_param.2018-05-28.xml: Referenced param does not " \
        "exist 'a.b'"


def test_xml_validation_unexistent_dependency():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_dep.2018-05-28.xml')

    assert str(cm.value) == \
        "xml/condition_not_dep.2018-05-28.xml: Referenced dependency does " \
        "not exist 'a.b'"


def test_xml_validation_invalid_condition():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_not_valid.2018-05-28.xml')

    assert str(cm.value) == \
        'xml/condition_not_valid.2018-05-28.xml: Lex error in condition'


def test_xml_validation_no_hyphen_in_id():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/validate_hyphen_id.2018-06-13.xml')

    assert str(cm.value) == \
        'xml/validate_hyphen_id.2018-06-13.xml: Id must be a valid variable ' \
        'name'


def test_xml_validation_no_hyphen_in_field_name():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/validate_hyphen_field.2018-06-13.xml')

    assert str(cm.value) == \
        'xml/validate_hyphen_field.2018-06-13.xml: Field names must be ' \
        'valid variable names'


def test_xml_validation_no_hyphen_in_form_id():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/validate_hyphen_form.2018-06-13.xml')

    assert str(cm.value) == \
        'xml/validate_hyphen_form.2018-06-13.xml: Form ids must be valid ' \
        'variable names'


def test_xml_validation_no_hyphen_in_grammar():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/validate_hyphen_if_condition.2018-06-13.xml')

    assert str(cm.value) == \
        'xml/validate_hyphen_if_condition.2018-06-13.xml: Lex error in ' \
        'condition'


def test_xml_validation_undefined_form():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_undefined_form.2018-07-10.xml')

    assert str(cm.value) == \
        'xml/condition_undefined_form.2018-07-10.xml: variable used in if is' \
        ' not defined \'misterio.password\''


def test_xml_validation_undefined_form_by_scope():
    with pytest.raises(SystemExit) as cm:
        xml_validate('xml/condition_undefined_form_by_scope.2018-07-10.xml')

    assert str(cm.value) == \
        'xml/condition_undefined_form_by_scope.2018-07-10.xml: some error'
