from xml.dom.minidom import Document
import pytest

from cacahuate.xml import Xml
from cacahuate.node import make_node
from cacahuate.models import Execution, Questionaire
from cacahuate.handler import Handler


def test_make_node_requires_existent_class():
    element = Document().createElement('foo')

    with pytest.raises(ValueError) as e:
        make_node(element)


def test_find_next_element_normal(config):
    ''' given a node, retrieves the next element in the graph, assumes that
    the element only has one outgoing edge '''
    xml = Xml.load(config, 'simple')
    handler = Handler(config)
    execution = Execution().save()

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'mid-node'
    ))

    values = handler.next(xml, current_node, execution)

    assert len(values) == 1
    assert values[0].id == 'final-node'


@pytest.mark.skip
def test_find_next_element_condition(config):
    ''' finding next element runs a node whose condition is satisfied '''
    xml = Xml.load(config, 'decision')
    handler = Handler(config)
    execution = Execution().save()

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'start-node'
    ))

    values = handler.next(xml, current_node, execution)

    assert len(values) == 1
    assert values[0].id == 'mid-node'


@pytest.mark.skip
def test_find_next_element_condition_unsatisfied(config):
    ''' given an if and asociated data, retrieves the next element, negative
    variant '''
    xml = Xml.load(config, 'decision')
    handler = Handler(config)
    execution = Execution().save()

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'start-node'
    ))

    values = handler.next(xml, current_node, execution)

    assert len(values) == 1
    assert values[0].id == 'final-node'


def test_find_next_element_end_explicit(config):
    ''' given an end element, return end signal '''
    xml = Xml.load(config, 'exit')
    handler = Handler(config)
    execution = Execution().save()

    assert xml.filename == 'exit.2018-05-03.xml'

    current_node = make_node(xml.find(
        lambda e: e.tagName == 'exit'
    ))

    nodes = handler.next(xml, current_node, execution)

    assert nodes == []


def test_find_next_element_end_implicit(config):
    ''' happens when the process gets to the final node '''
    xml = Xml.load(config, 'exit')
    handler = Handler(config)
    execution = Execution().save()

    assert xml.filename == 'exit.2018-05-03.xml'

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'final-node'
    ))

    nodes = handler.next(xml, current_node, execution)

    assert nodes == []


def test_find_next_element_data_invalidation(config):
    assert False
