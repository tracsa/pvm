""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
import case_conversion
from typing import Iterator
from xml.dom.minidom import Element

from cacahuate.xml import Xml, get_text
from cacahuate.logger import log
from cacahuate.grammar import Condition
from cacahuate.errors import ElementNotFound, IncompleteBranch


class Node:
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element):
        self.element = element

    def next(self, xmliter: Iterator[Element], execution) -> ['Node']:
        ''' Gets the next node in the graph,
        if it fails raises an exception.'''
        raise NotImplementedError('Should be implemented for subclasses')


class EndNode(Node):

    def next(self, xml, execution):
        return []


class SimpleNode(Node):

    def next(self, xml: Xml, execution) -> ['Node']:
        ''' just find the next node in the graph '''
        def find_node(e):
            if e.tagName != 'connector':
                return False

            return e.getAttribute('from') == self.element.getAttribute('id')

        conn = xml.find(find_node)

        return [(False, make_node(xml.find(
            lambda e: e.getAttribute('id') == conn.getAttribute('to')
        )))]


class DecisionNode(Node):

    def next(self, xml: Xml, execution) -> ['Node']:
        ''' find node whose value corresponds to the answer '''
        def find_node(el):
            if el.tagName != 'connector':
                return False

            if el.getAttribute('from') != self.element.getAttribute('id'):
                return False

            cons = el.getElementsByTagName('condition')

            if len(cons) != 1:
                return False

            con = cons[0]

            return Condition(execution).parse(get_text(con))

        try:
            conn = xml.find(find_node)
        except ElementNotFound:
            raise IncompleteBranch(
                'Either not all branches for this desition are defined or '
                'there is not enough information in the asociated data'
            )

        return [(False, make_node(xml.find(
            lambda e: e.getAttribute('id') == conn.getAttribute('to')
        )))]


class GotoNode(Node):

    def next(self, xml: Xml, execution) -> ['Node']:
        ''' tries to find an element back in time '''
        def find_node(e):
            if e.tagName != 'connector':
                return False

            return e.getAttribute('from') == self.element.getAttribute('id')

        conn = xml.find(find_node)

        rewinded = Xml(xml.config, xml.filename)
        del xml

        return [(True, make_node(rewinded.find(
            lambda e: e.getAttribute('id') == conn.getAttribute('to')
        )))]


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if not element.getAttribute('class'):
        raise KeyError('Must have the class atrribute')

    class_name = case_conversion.pascalcase(
                                            element.getAttribute('class')
                ) + 'Node'
    available_classes = __import__(__name__).node

    if class_name not in dir(available_classes):
        raise ValueError('Class definition not found: {}'.format(class_name))

    return getattr(available_classes, class_name)(
        element
    )
