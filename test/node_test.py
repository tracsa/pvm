from xml.dom.minidom import Document
import pytest

from cacahuate.node import make_node, Node
from cacahuate.xml import Xml
from cacahuate.models import Execution, Questionaire


def test_make_node_requires_class():
    element = Document().createElement('node')

    with pytest.raises(KeyError) as e:
        make_node(element)


def test_make_node_requires_existent_class():
    element = Document().createElement('node')
    element.setAttribute('class', 'foo')

    with pytest.raises(ValueError) as e:
        make_node(element)


def test_find_next_element_normal(config):
    ''' given a node, retrieves the next element in the graph, assumes that
    the element only has one outgoing edge '''
    xml = Xml.load(config, 'simple')

    assert xml.filename == 'simple.2018-02-19.xml'

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'mid-node'
    ))

    assert current_node.element.getAttribute('id') == 'mid-node'

    is_backwards, next_node = current_node.next(xml, None)[0]

    assert is_backwards is False
    assert next_node.element.getAttribute('id') == 'end-node'


def test_find_next_element_decision_yes(config, models):
    ''' given an if and asociated data, retrieves the next element '''
    xml = Xml.load(config, 'decision')
    exc = Execution().save()
    form = Questionaire(ref="fork", data={'proceed': 'yes'}).save()
    form.proxy.execution.set(exc)

    assert xml.filename == 'decision.2018-02-27.xml'

    current_node = make_node(xml.find(
        lambda e:
        e.tagName == 'node' and e.getAttribute('id') == '57TJ0V3nur6m7wvv'
    ))

    is_backwards, next_node = current_node.next(xml, exc)[0]

    assert is_backwards is False
    assert next_node.element.getAttribute('id') == 'Cuptax0WTCL1ueCy'


def test_find_next_element_decision_no(config, models):
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


def test_find_next_element_end(config):
    ''' given an end element, return end signal '''
    xml = Xml.load(config, 'decision')
    exc = Execution().save()

    assert xml.filename == 'decision.2018-02-27.xml'

    current_node = make_node(xml.find(
        lambda e:
        e.tagName == 'node' and e.getAttribute('id') == 'BCUHAjo4OxtA31NR'
    ))

    nodes = current_node.next(xml, exc)

    assert nodes == []


@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_subprocess_noready():
    ''' given a subprocess node and a subprocess that havent completed yet,
    return None '''


@pytest.mark.skip(reason="no way of currently testing this")
def test_find_next_element_subprocess_ready():
    ''' given a subprocess node and a subprocess that has been completed,
    return the next node '''


def test_find_next_element_goto(config):
    ''' given a goto element that points to a previous node in the graph,
    return that element '''
    xml = Xml.load(config, 'cyclic')
    exc = Execution().save()

    current_node = make_node(xml.find(
        lambda e: e.getAttribute('id') == 'jump-node'
    ))

    is_backwards, next_node = current_node.next(xml, exc)[0]

    assert is_backwards is True
    assert next_node.element.getAttribute('id') == 'start-node'
