from io import TextIOWrapper
import os
import pytest
import json

from pvm.errors import ProcessNotFound
from pvm.xml import Xml, etree_from_list, nodes_from, has_no_incoming, has_edges, topological_sort, form_to_dict
from xml.dom.minidom import parse

def test_load_not_found(config):
    ''' if a process file is not found, raise an exception '''
    with pytest.raises(ProcessNotFound):
        Xml.load(config, 'notfound')

def test_load_process(config):
    '''  a process file can be found using only its prefix or common name '''
    xml = Xml.load(config, 'simple')

    assert xml.filename == 'simple.2018-02-19.xml'
    assert xml.public == False

def test_load_last_matching_process(config):
    ''' a process is specified by its common name, but many versions may exist.
    when a process is requested for start we must use the last version of it '''
    xml = Xml.load(config, 'oldest')

    assert xml.filename == 'oldest.2018-02-17.xml'
    assert xml.public == False

def test_load_specific_version(config):
    ''' one should be able to request a specific version of a process,
    thus overriding the process described by the previous test '''
    xml = Xml.load(config, 'oldest.2018-02-14')

    assert xml.filename == 'oldest.2018-02-14.xml'
    assert xml.public == False

def test_make_iterator(config):
    ''' test that the iter function actually returns an interator over the
    nodes and edges of the process '''
    xml = Xml.load(config, 'simple')

    expected_nodes = [
        'node',
        'connector',
        'node',
        'connector',
        'node',
    ]

    for given, expected in zip(xml, expected_nodes):
        assert given.tagName == expected

def test_find(config):
    xml = Xml.load(config, 'simple')

    start = xml.find(lambda e:e.tagName=='node')

    assert start.tagName == 'node'
    assert start.getAttribute('id') == 'gYcj0XjbgjSO'

    conn = xml.find(
        lambda e:e.tagName=='connector' and e.getAttribute('from')==start.getAttribute('id')
    )

    assert conn.tagName == 'connector'
    assert conn.getAttribute('from') == 'gYcj0XjbgjSO'
    assert conn.getAttribute('to') == '4g9lOdPKmRUf'

    echo = xml.find(
        lambda e:e.getAttribute('id')==conn.getAttribute('to')
    )

    assert echo.tagName == 'node'
    assert echo.getAttribute('id') == '4g9lOdPKmRUf'

    conn = xml.find(
        lambda e:e.tagName=='connector' and e.getAttribute('from')==echo.getAttribute('id')
    )

    assert conn.tagName == 'connector'
    assert conn.getAttribute('from') == '4g9lOdPKmRUf'
    assert conn.getAttribute('to') == 'kV9UWSeA89IZ'

    end = xml.find(
        lambda e:e.getAttribute('id')==conn.getAttribute('to')
    )

    assert end.tagName == 'node'
    assert end.getAttribute('id') == 'kV9UWSeA89IZ'

def test_list_processes(config):
    processes = Xml.list(config)

    assert processes == [
        {
            'id': 'exit_request',
            'version': '2018-03-20',
            'author': 'categulario',
            'date': '2018-03-20',
            'name': 'Petición de salida',
            'description': 'Este proceso es iniciado por un empleado que quiere salir temporalmente de la empresa (e.g. a comer). La autorización llega a su supervisor, quien autoriza o rechaza la salida, evento que es notificado de nuevo al empleado y finalmente a los guardias, uno de los cuales notifica que el empleado salió de la empresa.',
            'versions': ['2018-03-20'],
        },
    ]

@pytest.mark.skip
def test_etree_from_list_empty():
    nodes = []
    etree = etree_from_list(Element('process'), nodes)

    root = etree.getroot()
    assert root.tagName == 'process'

    for elem, expct in zip(root.iter(), nodes):
        assert elem.tagName == expct.tagName
        assert elem.id == expct.id

@pytest.mark.skip
def test_etree_from_list_withnodes():
    nodes = [
        Element('foo', attrib={'a': 0}),
        Element('var', attrib={'a': 1}),
        Element('log', attrib={'a': 2}),
    ]
    nodes[2].append(Element('sub'))

    etree = etree_from_list(Element('process'), nodes)

    root = etree.getroot()
    assert root.tagName == 'process'

    for i, (elem, expct) in enumerate(zip(root, nodes)):
        assert elem.tagName == expct.tagName
        assert elem.getAttribute('a') == i

    ch = root[2][0]
    assert ch.tagName == 'sub'

@pytest.mark.skip
def test_nodes_from(config):
    xml = parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    start_node = list(xml.getroot())[10]

    assert start_node.getAttribute('id') == 'B'

    given = list(nodes_from(start_node, xml.getroot()))
    expct = [
        (Element('node', {'id':'D'}), Element('connector', {'id':'B-D'})),
        (Element('node', {'id':'C'}), Element('connector', {'id':'B-C'})),
        (Element('node', {'id':'E'}), Element('connector', {'id':'B-E'})),
    ]

    assert len(given) == len(expct)

    for (node, edge), (expct_node, expct_edge) in zip(given, expct):
        assert node.getAttribute('id') == expct_node.getAttribute('id')
        assert edge.getAttribute('id') == expct_edge.getAttribute('id')

@pytest.mark.skip
def test_has_no_incoming_sorted(config):
    xml = parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert has_no_incoming(Element('node', {'id':'A'}), xml.getroot()) == True
    assert has_no_incoming(Element('node', {'id':'B'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'C'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'D'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'E'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'F'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'G'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'H'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'I'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'J'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'K'}), xml.getroot()) == False

@pytest.mark.skip
def test_has_no_incoming_unsorted(config):
    xml = parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    assert has_no_incoming(Element('node', {'id':'A'}), xml.getroot()) == True
    assert has_no_incoming(Element('node', {'id':'B'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'C'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'D'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'E'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'F'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'G'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'H'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'I'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'J'}), xml.getroot()) == False
    assert has_no_incoming(Element('node', {'id':'K'}), xml.getroot()) == False

@pytest.mark.skip
def test_has_edges(config):
    sortedxml = parse(os.path.join(config['XML_PATH'], 'sorted.xml'))
    unsorted = parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    no_edges = parse(os.path.join(config['XML_PATH'], 'no_edges.xml'))

    assert has_edges(sortedxml) == True
    assert has_edges(unsorted) == True
    assert has_edges(no_edges) == False

@pytest.mark.skip
def test_toposort(config):
    xml = parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    new_xml = topological_sort(xml.find(".//*[@id='A']"), xml.getroot())

    expct_tree = parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert len(new_xml.getroot()) == len(expct_tree.getroot())
    assert len(new_xml.getroot()) == 21

    for elem, expct in zip(new_xml.iter(), expct_tree.iter()):
        assert elem.tagName == expct.tagName
        assert elem.attrib == expct.attrib

def test_form_to_dict(config):
    xml = parse(os.path.join(config['XML_PATH'], 'testing_forms.xml'))
    forms = xml.getElementsByTagName('form')

    dict_forms = list(map(
        form_to_dict,
        forms,
    ))

    assert dict_forms[0] == {
        'ref': '#text-input',
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
        "ref": "#two-inputs",
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
        "ref": "#select",
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
