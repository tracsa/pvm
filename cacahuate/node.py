""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
from case_conversion import pascalcase
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
        return [(False, make_node(next(xml))]


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if not element.getAttribute('class'):
        raise KeyError('Must have the class atrribute')

    class_name = pascalcase(element.getAttribute('class')) + 'Node'
    available_classes = __import__(__name__).node

    if class_name not in dir(available_classes):
        raise ValueError('Class definition not found: {}'.format(class_name))

    return getattr(available_classes, class_name)(element)
