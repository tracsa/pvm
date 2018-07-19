import os
import pytest

from cacahuate.errors import ProcessNotFound
from xml.dom.minidom import parse
from cacahuate.xml import Xml, form_to_dict


def test_load_not_found(config):
    ''' if a process file is not found, raise an exception '''
    with pytest.raises(ProcessNotFound):
        Xml.load(config, 'notfound')


def test_load_process(config):
    '''  a process file can be found using only its prefix or common name '''
    xml = Xml.load(config, 'simple')

    assert xml.filename == 'simple.2018-02-19.xml'
    assert xml.public is True


def test_load_last_matching_process(config):
    ''' a process is specified by its common name, but many versions may exist.
    when a process is requested for start we must use the last version of it
    '''
    xml = Xml.load(config, 'oldest')

    assert xml.filename == 'oldest.2018-02-17.xml'
    assert xml.public is False


def test_load_respects_name(config):
    ''' if there are two xmls whose name starts with the same prefix, the one
    matching the exact name should be resolved '''
    xml = Xml.load(config, 'exit')

    assert xml.filename == 'exit.2018-05-03.xml'


def test_load_specific_version(config):
    ''' one should be able to request a specific version of a process,
    thus overriding the process described by the previous test '''
    xml = Xml.load(config, 'oldest.2018-02-14')

    assert xml.filename == 'oldest.2018-02-14.xml'
    assert xml.public is False


def test_make_iterator(config):
    ''' test that the iter function actually returns an interator over the
    nodes and edges of the process '''
    xml = Xml.load(config, 'simple')

    expected_nodes = [
        'action',
        'action',
    ]

    for given, expected in zip(xml, expected_nodes):
        assert given.tagName == expected


def test_find(config):
    xmliter = iter(Xml.load(config, 'simple'))

    start = next(xmliter)

    assert start.tagName == 'action'
    assert start.getAttribute('id') == 'start_node'

    echo = xmliter.find(
        lambda e: e.getAttribute('id') == 'mid_node'
    )

    assert echo.tagName == 'action'
    assert echo.getAttribute('id') == 'mid_node'

    end = xmliter.find(
        lambda e: e.getAttribute('id') == 'final_node'
    )

    assert end.tagName == 'action'
    assert end.getAttribute('id') == 'final_node'


def test_skip_else(config):
    xmliter = iter(Xml.load(config, 'else'))

    xmliter.find(lambda x: x.getAttribute('id') == 'action01')

    with pytest.raises(StopIteration):
        xmliter.next_skipping_elifelse()


def test_form_to_dict(config):
    xml = parse(os.path.join(config['XML_PATH'], 'all-inputs.2018-04-04.xml'))
    forms = xml.getElementsByTagName('form')

    dict_forms = list(map(
        form_to_dict,
        forms,
    ))

    assert dict_forms[0] == {
        'ref': 'auth_form',
        'inputs': [
            {
                "type": "text",
                "name": "name",
                "label": "Nombre",
                "required": True,
                "placeholder": "Jon Snow",
            },
            {
                'type': 'datetime',
                'name': 'datetime',
                'label': 'Fecha de nacimiento',
                "required": True,
            },
            {
                "label": "Un secreto",
                "type": "password",
                "name": "secret",
                "required": True,
            },
            {
                "type": "radio",
                "name": "gender",
                "required": True,
                "label": "Género?",
                "options": [
                    {
                        "value": "male",
                        "label": "Masculino",
                    },
                    {
                        "value": "female",
                        "label": "Femenino",
                    },
                ],
            },
            {
                "type": "checkbox",
                "name": "interests",
                "required": True,
                "label": "Marque sus intereses",
                "options": [
                    {"value": "science", "label": "Ciencia"},
                    {"value": "sports", "label": "Deportes"},
                    {"value": "music", "label": "Música"},
                    {"value": "nature", "label": "Naturaleza"},
                    {"value": "thecnology", "label": "Tecnología"},
                ],
            },
            {
                "type": "select",
                "name": "elections",
                "required": True,
                "label": "Emita su voto",
                "options": [
                    {
                        "value": "amlo",
                        "label": "Andrés Manuel López Obrador",
                    },
                    {
                        "value": "meade",
                        "label": "José Antonio Meade Kuribreña",
                    },
                    {
                        "value": "marguarita",
                        "label": "Margarita Ester Zavala Gómez del Campo",
                    },
                    {
                        "value": "anaya",
                        "label": "Ricardo Anaya Cortés",
                    },
                ],
            },
            {
                'label': 'Un entero',
                'type': 'int',
                'required': True,
                'name': 'int',
            },
            {
                'label': 'Un flotante',
                'type': 'float',
                'required': True,
                'name': 'float',
            },
        ]
    }


def test_get_state(config):
    xml = Xml.load(config, 'milestones')

    assert xml.get_state() == {
        '_type': ':sorted_map',
        'items': {
            'start': {
                '_type': 'node',
                'actors': {'_type': ':map', 'items': {}},
                'comment': '',
                'id': 'start',
                'state': 'unfilled',
                'type': 'action',
                'milestone': False,
                'name': '',
                'description': '',
            },
            'end': {
                '_type': 'node',
                'actors': {'_type': ':map', 'items': {}},
                'comment': '',
                'id': 'end',
                'state': 'unfilled',
                'type': 'validation',
                'milestone': True,
                'name': '',
                'description': '',
            },
        },
        'item_order': ['start', 'end'],
    }
