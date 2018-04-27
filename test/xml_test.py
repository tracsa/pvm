from io import TextIOWrapper
import os
import pytest
import simplejson as json

from cacahuate.errors import ProcessNotFound
from xml.dom.minidom import parse
from cacahuate.models import Execution, User, Activity
from cacahuate.xml import Xml, resolve_params, form_to_dict


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
        'node',
        'node',
    ]

    for given, expected in zip(xml, expected_nodes):
        assert given.tagName == expected


def test_find(config):
    xml = Xml.load(config, 'simple')

    start = xml.start_node

    assert start.tagName == 'node'
    assert start.getAttribute('id') == 'start-node'

    echo = xml.find(
        lambda e: e.getAttribute('id') == 'mid-node'
    )

    assert echo.tagName == 'node'
    assert echo.getAttribute('id') == 'mid-node'

    end = xml.find(
        lambda e: e.getAttribute('id') == 'final-node'
    )

    assert end.tagName == 'node'
    assert end.getAttribute('id') == 'final-node'


def test_form_to_dict(config):
    xml = parse(os.path.join(config['XML_PATH'], 'all-inputs.2018-04-04.xml'))
    forms = xml.getElementsByTagName('form')

    dict_forms = list(map(
        form_to_dict,
        forms,
    ))

    assert dict_forms[0] == {
        'ref': 'auth-form',
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
                        "label": "Andres Manuel López Obrador",
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
        ]
    }


def test_resolve_params(config):
    xml = Xml.load(config, 'simple.2018-02-19.xml')

    el = xml.find(lambda e: e.getAttribute('id') == 'mid-node')
    filter_node = el.getElementsByTagName('auth-filter')[0]

    execution = Execution().save()
    juan = User(identifier='juan').save()
    act = Activity(ref='start-node').save()
    act.proxy.user.set(juan)
    act.proxy.execution.set(execution)

    assert resolve_params(filter_node, execution) == {
        'identifier': 'juan',
        'relation': 'manager',
    }
