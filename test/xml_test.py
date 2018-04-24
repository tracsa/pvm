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
    assert xml.public is False


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
        'connector',
        'node',
        'connector',
        'node',
    ]

    for given, expected in zip(xml, expected_nodes):
        assert given.tagName == expected


def test_find(config):
    xml = Xml.load(config, 'simple')

    start = xml.start_node

    assert start.tagName == 'node'
    assert start.getAttribute('id') == 'start-node'

    conn = xml.find(
        lambda e:
        e.tagName == 'connector' and
            e.getAttribute('from') == start.getAttribute('id')
    )

    assert conn.tagName == 'connector'
    assert conn.getAttribute('from') == 'start-node'
    assert conn.getAttribute('to') == 'mid-node'

    echo = xml.find(
        lambda e: e.getAttribute('id') == conn.getAttribute('to')
    )

    assert echo.tagName == 'node'
    assert echo.getAttribute('id') == 'mid-node'

    conn = xml.find(
        lambda e:
        e.tagName == 'connector' and
            e.getAttribute('from') == echo.getAttribute('id')
    )

    assert conn.tagName == 'connector'
    assert conn.getAttribute('from') == 'mid-node'
    assert conn.getAttribute('to') == 'end-node'

    end = xml.find(
        lambda e: e.getAttribute('id') == conn.getAttribute('to')
    )

    assert end.tagName == 'node'
    assert end.getAttribute('id') == 'end-node'


def test_form_to_dict(config):
    xml = parse(os.path.join(config['XML_PATH'], 'testing_forms.xml'))
    forms = xml.getElementsByTagName('form')

    dict_forms = list(map(
        form_to_dict,
        forms,
    ))

    assert dict_forms[0] == {
        'ref': 'text-input',
        'inputs': [
            {
                'type': 'text',
                'name': 'ccn',
                'regex': '[0-9]{16}',
                'label': 'credit card number',
            },
        ],
    }

    assert dict_forms[1] == {
        "ref": "two-inputs",
        "inputs": [
            {
                "type": "text",
                "name": "firstname"
            },
            {
                "type": "text",
                "name": "surname"
            }
        ]
    }

    assert dict_forms[2] == {
        "ref": "select",
        "inputs": [
            {
                "type": "radio",
                "name": "auth",
                "required": True,
                "label": "Le das chance?",
                "options": [
                    {
                        "value": "yes",
                        "label": "Ándale mijito, ve",
                    },
                    {
                        "value": "no",
                        "label": "Ni madres",
                    },
                ],
            },
        ]
    }

    assert dict_forms[3] == {
        "ref": "with-helper",
        "inputs": [
            {
                "type": "password",
                "name": "password",
                "helper": "10 alfanumeric chars",
            },
        ]
    }


def test_resolve_params(config):
    xml = Xml.load(config, 'exit_request.2018-03-20.xml')

    el = xml.find(lambda e: e.getAttribute('id') == 'manager')
    filter_node = el.getElementsByTagName('auth-filter')[0]

    execution = Execution().save()
    juan = User(identifier='juan').save()
    act = Activity(ref='requester').save()
    act.proxy.user.set(juan)
    act.proxy.execution.set(execution)

    assert resolve_params(filter_node, execution) == {
        'identifier': 'juan',
        'relation': 'manager',
    }
