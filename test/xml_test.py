from itacate import Config
from xml.etree import ElementTree
import os
import tempfile

from .context import lib

def get_testing_config(overwrites:dict=None):
    config = Config(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
    config.from_pyfile('settings.py')

    if overwrites is not None:
        config.from_mapping(overwrites)

    return config

#-------
# Tests
#-------

def test_get_nodes_and_edges():
    config = get_testing_config()
    expctnodes = [ "A", "G", "F", "I", "B", "D", "K", "E", "H", "C", "J" ]
    expctedges = [ "A-B", "I-K", "H-J", "B-D", "C-G", "B-C", "C-F", "G-H", "G-I", "B-E" ]

    with open(os.path.join(config['XML_PATH'], 'unsorted.xml')) as xmlfile:
        nodes, edges = lib.xml.get_nodes_and_edges(xmlfile)

    assert len(nodes) == len(expctnodes)
    assert len(edges) == len(expctedges)

    for node, expctnode in zip(nodes, expctnodes):
        assert node.attrib['id'] == expctnode

    for edge, expctedge in zip(edges, expctedges):
        assert edge.attrib['id'] == expctedge

def test_etree_from_list():
    assert False

def test_toposort():
    config = get_testing_config()

    with open(os.path.join(config['XML_PATH'], 'unsorted.xml')) as xmlfile:
        new_xml = lib.xml.topological_sort(*lib.xml.get_nodes_and_edges(xmlfile))

    expct = os.path.join(config['XML_PATH'], 'sorted.xml')

    with tempfile.TemporaryFile() as tmpf, open(expct) as expctf:
        new_xml.write(tmpf)
        tmpf.seek(0)

        assert tmpf.read() == expctf.read()

    assert new_xml.write()

def test_find_next_element_normal():
    ''' given a node, retrieves the next element in the graph '''
    lib.xml.XML(config)
    assert 1==1

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
