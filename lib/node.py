""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
import case_conversion
import xml.etree.ElementTree as ET
from typing import Iterator

from .process import find
from .logger import log


class Node:
    ''' A node from the process's graph. It is initialized from an ET.Element
    '''

    def __init__(self, id, attrib):
        self.id = id
        self.attrib = attrib

    def __call__(self):
        ''' Executes this node's action. Can be triggering a message or
        something similar '''
        raise NotImplementedError('Should be implemented for subclasses')

    def can_continue(self):
        ''' Determines if this node has everything it needs to continue the
        execution of the script '''
        raise NotImplementedError('Should be implemented for subclasses')

    def next(self, xmliter:Iterator[ET.Element]) -> ['Node']:
        ''' Gets the next node in the graph, if it fails raises an exception.
        Assumes that can_continue() has been called before '''
        raise NotImplementedError('Should be implemented for subclasses')

    def is_end(self) -> bool:
        ''' tells if this node is the final node of the graph '''
        return False


class NonBlockingNode(Node):
    ''' Nodes that don't wait for external info to execute '''

    def can_continue(self):
        ''' start nodes have everything they need to continue '''
        return True


class SingleConnectedNode(Node):

    def next(self, xmliter:Iterator[ET.Element]) -> ['Node']:
        ''' just find the next node in the graph '''
        conn = find(xmliter, lambda e:e.attrib['from'] == self.id)
        return [make_node(find(xmliter, lambda e:e.attrib['id'] == conn.attrib['to']))]


class StartNode(NonBlockingNode, SingleConnectedNode):
    ''' Each process graph should contain one and only one start node which is
    the head and trigger of everything. It only leads to the next step in the
    execution '''


class DummyNode(NonBlockingNode, SingleConnectedNode):
    '''a node that does nothing but stand there... waiting for the appropiate
    moment for... doing nothing '''


class EchoNode(NonBlockingNode, SingleConnectedNode):

    def __call__(self):
        log.debug(self.attrib['msg'])


class EndNode(Node):

    def __call__(self): pass

    def is_end(self):
        return True


def make_node(element):
    ''' returns a build Node object given an ET.Element object '''
    if 'class' not in element.attrib:
        raise KeyError('Must have the class atrribute')

    class_name = case_conversion.pascalcase(element.attrib['class']) + 'Node'
    available_classes = __import__(__name__).node

    if class_name not in dir(available_classes):
        raise ValueError('Class definition not found: {}'.format(class_name))

    return getattr(available_classes, class_name)(
        element.attrib.get('id'),
        element.attrib,
    )
