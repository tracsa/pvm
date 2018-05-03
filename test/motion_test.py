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


def test_find_next_element_condition(config):
    ''' finding next element runs a node whose condition is satisfied '''
    xml = Xml.load(config, 'decision')
    exc = Execution().save()
    form = Questionaire(ref="fork", data={'proceed': 'yes'}).save()
    form.proxy.execution.set(exc)

    assert xml.filename == 'decision.2018-04-26.xml'

    current_node = make_node(xml.find(
        lambda e:
        e.tagName == 'node' and e.getAttribute('id') == '57TJ0V3nur6m7wvv'
    ))

    is_backwards, next_node = current_node.next(xml, exc)[0]

    assert is_backwards is False
    assert next_node.element.getAttribute('id') == 'Cuptax0WTCL1ueCy'


def test_find_next_element_condition_unsatisfied(config):
    ''' given an if and asociated data, retrieves the next element, negative
    variant '''
    xml = Xml.load(config, 'decision')
    exc = Execution().save()
    form = Questionaire(ref="fork", data={'proceed': 'no'}).save()
    form.proxy.execution.set(exc)

    assert xml.filename == 'decision.2018-02-27.xml'

    current_node = make_node(xml.find(
        lambda e:
        e.tagName == 'node' and e.getAttribute('id') == '57TJ0V3nur6m7wvv'
    ))

    is_backwards, next_node = current_node.next(xml, exc)[0]

    assert is_backwards is False
    assert next_node.element.getAttribute('id') == 'mj88CNZUaBdvLV83'


def test_find_next_element_data_invalidation(config):
    assert False


def test_find_next_element_end_explicit(config):
    ''' given an end element, return end signal '''
    xml = Xml.load(config, 'decision')
    exc = Execution().save()

    assert xml.filename == 'decision.2018-04-26.xml'

    current_node = make_node(xml.find(
        lambda e:
        e.tagName == 'exit'
    ))

    nodes = current_node.next(xml, exc)

    assert nodes == []


def test_find_next_element_end_implicit(config):
    ''' happens when the process gets to the final node '''
    assert False
