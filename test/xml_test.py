import xml.etree.ElementTree as ET
import os

from .context import lib, get_testing_config

def test_etree_from_list_empty():
    nodes = []
    etree = lib.xml.etree_from_list(ET.Element('process'), nodes)

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

    etree = lib.xml.etree_from_list(ET.Element('process'), nodes)

    root = etree.getroot()
    assert root.tag == 'process'

    for i, (elem, expct) in enumerate(zip(root, nodes)):
        assert elem.tag == expct.tag
        assert elem.attrib['a'] == i

    ch = root[2][0]
    assert ch.tag == 'sub'

def test_nodes_from():
    config = get_testing_config()
    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    start_node = list(xml.getroot())[10]

    assert start_node.attrib['id'] == 'B'

    given = list(lib.xml.nodes_from(start_node, xml.getroot()))
    expct = [
        (ET.Element('node', {'id':'D'}), ET.Element('connector', {'id':'B-D'})),
        (ET.Element('node', {'id':'C'}), ET.Element('connector', {'id':'B-C'})),
        (ET.Element('node', {'id':'E'}), ET.Element('connector', {'id':'B-E'})),
    ]

    assert len(given) == len(expct)

    for (node, edge), (expct_node, expct_edge) in zip(given, expct):
        assert node.attrib['id'] == expct_node.attrib['id']
        assert edge.attrib['id'] == expct_edge.attrib['id']

def test_has_no_incoming_sorted():
    config = get_testing_config()
    xml = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'A'}), xml.getroot()) == True
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'B'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'C'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'D'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'E'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'F'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'G'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'H'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'I'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'J'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'K'}), xml.getroot()) == False

def test_has_no_incoming_unsorted():
    config = get_testing_config()
    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))

    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'A'}), xml.getroot()) == True
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'B'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'C'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'D'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'E'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'F'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'G'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'H'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'I'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'J'}), xml.getroot()) == False
    assert lib.xml.has_no_incoming(ET.Element('node', {'id':'K'}), xml.getroot()) == False

def test_has_edges():
    config = get_testing_config()
    sortedxml = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))
    unsorted = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    no_edges = ET.parse(os.path.join(config['XML_PATH'], 'no_edges.xml'))

    assert lib.xml.has_edges(sortedxml) == True
    assert lib.xml.has_edges(unsorted) == True
    assert lib.xml.has_edges(no_edges) == False

def test_toposort():
    config = get_testing_config()

    xml = ET.parse(os.path.join(config['XML_PATH'], 'unsorted.xml'))
    new_xml = lib.xml.topological_sort(xml.find(".//*[@id='A']"), xml.getroot())

    expct_tree = ET.parse(os.path.join(config['XML_PATH'], 'sorted.xml'))

    assert len(new_xml.getroot()) == len(expct_tree.getroot())
    assert len(new_xml.getroot()) == 21

    for elem, expct in zip(new_xml.iter(), expct_tree.iter()):
        assert elem.tag == expct.tag
        assert elem.attrib == expct.attrib

def test_find_next_element_normal():
    ''' given a node, retrieves the next element in the graph, assumes that
    the element only has one outgoing edge '''
    lib.xml.XML(config)
    assert False

def test_find_next_element_if_true():
    ''' given an if and asociated data, retrieves the next element '''
    assert False

def test_find_next_element_if_false():
    ''' given an if and asociated data, retrieves the next element, negative
    variant '''
    assert False

def test_find_next_element_case():
    ''' given a case clause and asociated data, retrieves the next selected
    branch '''
    assert False

def test_find_next_element_multithread():
    ''' given a multithread element of the graph, returns pointers to each
    thread '''
    assert False

def test_find_next_element_join_noready():
    ''' given a multithread join element that has not collected all of its
    pointers, return a wait signal '''
    assert False

def test_find_next_element_join_ready():
    ''' given a multithread join element with all of its pointers, return a
    pointer to the next element '''
    assert False

def test_find_next_element_end():
    ''' given an end element, return end signal '''
    assert False

def test_find_next_element_subprocess_noready():
    ''' given a subprocess node and a subprocess that havent completed yet,
    return None '''

def test_find_next_element_subprocess_ready():
    ''' given a subprocess node and a subprocess that has been completed,
    return the next node '''

def test_find_next_element_goto():
    ''' given a goto element that points to a previous node in the graph,
    return that element '''
