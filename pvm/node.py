""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
import case_conversion
from typing import Iterator
from xml.dom.minidom import Element

from .xml import Xml
from .logger import log
from .errors import DataMissing, InvalidData


class Node:
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element):
        self.element = element

    def wakeup(self):
        ''' Executes this node's action. Can be triggering a message or
        something similar '''
        raise NotImplementedError('Should be implemented for subclasses')

    def validate(self, data:dict):
        ''' Determines if this node has everything it needs to continue the
        execution of the script '''
        raise NotImplementedError('Should be implemented for subclasses')

    def next(self, xmliter:Iterator[Element], data:dict) -> ['Node']:
        ''' Gets the next node in the graph, if it fails raises an exception.
        Assumes that validate() has been called before '''
        raise NotImplementedError('Should be implemented for subclasses')

    def is_end(self) -> bool:
        ''' tells if this node is the final node of the graph '''
        return False

    def is_async(self) -> bool:
        ''' returns true for nodes that require external output to continue '''
        raise NotImplementedError('Should be implemented for subclasses')


class SyncNode(Node):
    ''' Nodes that don't wait for external info to execute '''

    def validate(self, data:dict):
        ''' start nodes have everything they need to continue '''
        return True


class AsyncNode(Node):
    ''' Nodes that wait for external confirmation '''


class SingleConnectedNode(Node):

    def next(self, xml:Xml, data:dict) -> ['Node']:
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

    def wakeup(self):
        log.debug(self.getAttribute('msg'))


class DecisionNode(AsyncNode):

    def wakeup(self): pass

    def validate(self, data:dict):
        if 'answer'  not in data:
            raise DataMissing('answer')

        if data['answer'] not in ('yes', 'no'):
            raise InvalidData('answer', data['answer'])

        return True

    def next(self, xml:Xml, data:dict) -> ['Node']:
        ''' find node whose value corresponds to the answer '''
        conn = xml.find(
            lambda e:e.tagName=='connector' and e.getAttribute('from')==self.element.getAttribute('id') and e.getAttribute('value') == data['answer']
        )

        return [make_node(xml.find(
            lambda e:e.getAttribute('id') == conn.getAttribute('to')
        ))]


class EndNode(SyncNode):

    def wakeup(self): pass

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
