import xml.etree.ElementTree as ET
import pytest

from .context import *

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

def test_find_next_element_normal(config):
    ''' given a node, retrieves the next element in the graph, assumes that
    the element only has one outgoing edge '''
    filename, xmlfile = lib.process.load(config, 'simple')

    assert filename == 'simple_2018-02-19.xml'

    xmliter = lib.process.iter_nodes(xmlfile)

    current_node = lib.node.make_node(lib.process.find(
        xmliter,
        lambda e:e.tag=='node' and e.attrib['id']=='4g9lOdPKmRUf'
    ))

    next_node = current_node.next(xmliter, dict())[0]

    assert next_node.id == 'kV9UWSeA89IZ'

def test_find_next_element_decision_yes(config):
    ''' given an if and asociated data, retrieves the next element '''
    filename, xmlfile = lib.process.load(config, 'decision')

    assert filename == 'decision_2018-02-27.xml'

    xmliter = lib.process.iter_nodes(xmlfile)

    current_node = lib.node.make_node(lib.process.find(
        xmliter,
        lambda e:e.tag=='node' and e.attrib['id']=='57TJ0V3nur6m7wvv'
    ))

    next_node = current_node.next(xmliter, {
        'answer': 'yes',
    })[0]

    assert next_node.id == 'Cuptax0WTCL1ueCy'

def test_find_next_element_decision_no(config):
    ''' given an if and asociated data, retrieves the next element, negative
    variant '''
    filename, xmlfile = lib.process.load(config, 'decision')

    assert filename == 'decision_2018-02-27.xml'

    xmliter = lib.process.iter_nodes(xmlfile)

    current_node = lib.node.make_node(lib.process.find(
        xmliter,
        lambda e:e.tag=='node' and e.attrib['id']=='57TJ0V3nur6m7wvv'
    ))

    next_node = current_node.next(xmliter, {
        'answer': 'no',
    })[0]

    assert next_node.id == 'mj88CNZUaBdvLV83'

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_case():
    ''' given a case clause and asociated data, retrieves the next selected
    branch '''
    assert False

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_multithread():
    ''' given a multithread element of the graph, returns pointers to each
    thread '''
    assert False

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_join_noready():
    ''' given a multithread join element that has not collected all of its
    pointers, return a wait signal '''
    assert False

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_join_ready():
    ''' given a multithread join element with all of its pointers, return a
    pointer to the next element '''
    assert False

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_end():
    ''' given an end element, return end signal '''
    assert False

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_subprocess_noready():
    ''' given a subprocess node and a subprocess that havent completed yet,
    return None '''

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_subprocess_ready():
    ''' given a subprocess node and a subprocess that has been completed,
    return the next node '''

@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_goto():
    ''' given a goto element that points to a previous node in the graph,
    return that element '''
