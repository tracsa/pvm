import xml.etree.ElementTree as ET
import pytest

from .context import lib

def test_make_node_requires_class():
    element = ET.Element('node', {})

    with pytest.raises(KeyError) as e:
        lib.node.make_node(element)

def test_make_node_requires_existent_class():
    element = ET.Element('node', {
        'class': 'foo',
    })

    with pytest.raises(ValueError) as e:
        lib.node.make_node(element)

def test_make_start_node():
    element = ET.Element('node', {
        'class': 'start',
    })
    node = lib.node.make_node(element)

    assert node is not None
    assert isinstance(node, lib.node.Node)
    assert isinstance(node, lib.node.StartNode)

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
