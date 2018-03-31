""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
import case_conversion
from typing import Iterator
from xml.dom.minidom import Element

from pvm.xml import Xml
from pvm.logger import log
from pvm.grammar import Condition


class Node:
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element):
        self.element = element

    def next(self, xmliter:Iterator[Element], execution) -> ['Node']:
        ''' Gets the next node in the graph, if it fails raises an exception.'''
        raise NotImplementedError('Should be implemented for subclasses')

    def is_end(self) -> bool:
        ''' tells if this node is the final node of the graph '''
        return False

    def is_async(self) -> bool:
        ''' returns true for nodes that require external output to continue '''
        raise NotImplementedError('Should be implemented for subclasses')


class SyncNode(Node):
    ''' Nodes that don't wait for external info to execute '''


class AsyncNode(Node):
    ''' Nodes that wait for external confirmation '''


class SingleConnectedNode(Node):

    def next(self, xml:Xml, execution) -> ['Node']:
        ''' just find the next node in the graph '''
        conn = xml.find(lambda e:e.tagName=='connector' and e.getAttribute('from') == self.element.getAttribute('id'))

        return [make_node(xml.find(
            lambda e:e.getAttribute('id') == conn.getAttribute('to')
        ))]


class StartNode(SyncNode, SingleConnectedNode):
    ''' Each process graph should contain one and only one start node which is
    the head and trigger of everything. It only leads to the next step in the
    execution '''


class DummyNode(SyncNode, SingleConnectedNode):
    '''a node that does nothing but stand there... waiting for the appropiate
    moment for... doing nothing '''


class EchoNode(SyncNode, SingleConnectedNode):
    ''' Prints to console the parameter contained in the attribute msg '''


class DecisionNode(AsyncNode):

    def next(self, xml:Xml, execution) -> ['Node']:
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

            return Condition(execution).parse(con.firstChild.nodeValue)

        conn = xml.find(find_node)

        return [make_node(xml.find(
            lambda e:e.getAttribute('id') == conn.getAttribute('to')
        ))]


class EndNode(SyncNode):

    def is_end(self):
        return True


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if not element.getAttribute('class'):
        raise KeyError('Must have the class atrribute')

    class_name = case_conversion.pascalcase(element.getAttribute('class')) + 'Node'
    available_classes = __import__(__name__).node

    if class_name not in dir(available_classes):
        raise ValueError('Class definition not found: {}'.format(class_name))

    return getattr(available_classes, class_name)(
        element
    )
