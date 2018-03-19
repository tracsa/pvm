from io import TextIOWrapper
import os
import pytest
import xml.etree.ElementTree as ET

from pvm.errors import ProcessNotFound
from pvm.xml import Xml, etree_from_list, nodes_from, has_no_incoming, has_edges, topological_sort

def test_load_not_found(config):
    ''' if a process file is not found, raise an exception '''
    with pytest.raises(ProcessNotFound):
        Xml.load(config, 'notfound')

def test_load_process(config):
    '''  a process file can be found using only its prefix or common name '''
    xml = Xml.load(config, 'simple')

    assert xml.name == 'simple_2018-02-19.xml'
    assert type(xml) == Xml

def test_load_last_matching_process(config):
    ''' a process is specified by its common name, but many versions may exist.
    when a process is requested for start we must use the last version of it '''
    xml = Xml.load(config, 'oldest')

    root = ET.fromstring(xml.file.read())

    assert xml.name == 'oldest_2018-02-17.xml'
    assert root.tag == 'process-spec'
    assert root[0].tag == 'process-info'
    assert root[0][0].tag == 'author'
    assert root[0][0].text == 'categulario'
    assert root[0][1].tag == 'date'
    assert root[0][1].text == '2018-02-17'
    assert root[0][2].tag == 'name'
    assert root[0][2].text == 'Oldest process v2'
    assert root[1].tag == 'process'

def test_load_specific_version(config):
    ''' one should be able to request a specific version of a process,
    thus overriding the process described by the previous test '''
    xml = Xml.load(config, 'oldest_2018-02-14')

    root = ET.fromstring(xml.file.read())

    assert xml.name == 'oldest_2018-02-14.xml'
    assert root.tag == 'process-spec'
    assert root[0].tag == 'process-info'
    assert root[0][0].tag == 'author'
    assert root[0][0].text == 'categulario'
    assert root[0][1].tag == 'date'
    assert root[0][1].text == '2018-02-14'
    assert root[0][2].tag == 'name'
    assert root[0][2].text == 'Oldest process'
    assert root[1].tag == 'process'

def test_make_iterator(config):
    ''' test that the iter function actually returns an interator over the
    nodes and edges of the process '''
    xml = Xml.load(config, 'simple')

    expected_nodes = [
        ET.Element('node', {'id':"gYcj0XjbgjSO", 'class':"start"}),
        ET.Element('connector', {'from':"gYcj0XjbgjSO", 'to':"4g9lOdPKmRUf"}),
        ET.Element('node', {'id':"4g9lOdPKmRUf", 'class':"echo", 'msg':"cuca"}),
        ET.Element('connector', {'from':"4g9lOdPKmRUf", 'to':"kV9UWSeA89IZ"}),
        ET.Element('node', {'id':"kV9UWSeA89IZ", 'class':"end"}),
    ]

    for given, expected in zip(xml, expected_nodes):
        assert given.tag == expected.tag
        assert given.attrib == expected.attrib

def test_find(config):
    xml = Xml.load(config, 'simple')

    start = xml.find(lambda e:e.tag=='node')

    assert start.tag == 'node'
    assert start.attrib['id'] == 'gYcj0XjbgjSO'

    conn = xml.find(
        lambda e:e.tag=='connector' and e.attrib['from']==start.attrib['id']
    )

    assert conn.tag == 'connector'
    assert conn.attrib == { 'from':"gYcj0XjbgjSO", 'to':"4g9lOdPKmRUf" }

    echo = xml.find(
        lambda e:e.attrib['id']==conn.attrib['to']
    )

    assert echo.tag == 'node'
    assert echo.attrib['id'] == '4g9lOdPKmRUf'

    conn = xml.find(
        lambda e:e.tag=='connector' and e.attrib['from']==echo.attrib['id']
    )

    assert conn.tag == 'connector'
    assert conn.attrib == {'from':"4g9lOdPKmRUf", 'to':"kV9UWSeA89IZ"}

    end = xml.find(
        lambda e:e.attrib['id']==conn.attrib['to']
    )

    assert end.tag == 'node'
    assert end.attrib['id'] == 'kV9UWSeA89IZ'

def test_etree_from_list_empty():
    nodes = []
    etree = etree_from_list(ET.Element('process'), nodes)

    root = etree.getroot()
    assert root.tag == 'process'

    for elem, expct in zip(root.iter(), nodes):
        assert elem.tag == expct.tag
        assert elem.id == expct.id

def test_etree_from_list_withnodes():
    nodes = [
        ET.Element('foo', attrib={'a': 0}),
        ET.Element('var', attrib={'a': 1}),
        ET.Element('log', attrib={'a': 2}),
    ]
    nodes[2].append(ET.Element('sub'))

    etree = etree_from_list(ET.Element('process'), nodes)

    root = etree.getroot()
    assert root.tag == 'process'

    for i, (elem, expct) in enumerate(zip(root, nodes)):
        assert elem.tag == expct.tag
        assert elem.attrib['a'] == i

    ch = root[2][0]
    assert ch.tag == 'sub'

def test_nodes_from(config):
    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    start_node = list(xml.getroot())[10]

    assert start_node.attrib['id'] == 'B'

    given = list(nodes_from(start_node, xml.getroot()))
    expct = [
        (ET.Element('node', {'id':'D'}), ET.Element('connector', {'id':'B-D'})),
        (ET.Element('node', {'id':'C'}), ET.Element('connector', {'id':'B-C'})),
        (ET.Element('node', {'id':'E'}), ET.Element('connector', {'id':'B-E'})),
    ]

    assert len(given) == len(expct)

    for (node, edge), (expct_node, expct_edge) in zip(given, expct):
        assert node.attrib['id'] == expct_node.attrib['id']
        assert edge.attrib['id'] == expct_edge.attrib['id']

def test_has_no_incoming_sorted(config):
    xml = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert has_no_incoming(ET.Element('node', {'id':'A'}), xml.getroot()) == True
    assert has_no_incoming(ET.Element('node', {'id':'B'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'C'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'D'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'E'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'F'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'G'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'H'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'I'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'J'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'K'}), xml.getroot()) == False

def test_has_no_incoming_unsorted(config):
    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    assert has_no_incoming(ET.Element('node', {'id':'A'}), xml.getroot()) == True
    assert has_no_incoming(ET.Element('node', {'id':'B'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'C'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'D'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'E'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'F'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'G'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'H'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'I'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'J'}), xml.getroot()) == False
    assert has_no_incoming(ET.Element('node', {'id':'K'}), xml.getroot()) == False

def test_has_edges(config):
    sortedxml = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))
    unsorted = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    no_edges = ET.parse(os.path.join(config['XML_PATH'], 'no_edges.xml'))

    assert has_edges(sortedxml) == True
    assert has_edges(unsorted) == True
    assert has_edges(no_edges) == False

def test_toposort(config):
    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    new_xml = topological_sort(xml.find(".//*[@id='A']"), xml.getroot())

    expct_tree = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert len(new_xml.getroot()) == len(expct_tree.getroot())
    assert len(new_xml.getroot()) == 21

    for elem, expct in zip(new_xml.iter(), expct_tree.iter()):
        assert elem.tag == expct.tag
        assert elem.attrib == expct.attrib
