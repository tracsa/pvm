from typing import Iterator, TextIO, Callable
import os
from xml.dom import pulldom
from xml.dom.minidom import Element

from .errors import ProcessNotFound, ElementNotFound
from .mark import comment


class Xml:

    def __init__(self, config, filename):
        self.config = config
        self.name = filename
        self.parser = pulldom.parse(open(os.path.join(config['XML_PATH'], filename)))

    @classmethod
    def load(cls, config:dict, common_name:str) -> TextIO:
        ''' Loads an xml file and returns the corresponding TextIOWrapper for
        further usage. The file might contain multiple versions so the latest one
        is chosen.

        common_name is the prefix of the file to find. If multiple files with the
        same prefix are found the last in lexicographical order is returned.'''
        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        for filename in files:
            if filename.startswith(common_name):
                return Xml(config, filename)
        else:
            raise ProcessNotFound(common_name)

    def __next__(self):
        ''' Returns an inerator over the nodes and edges of a process defined
        by the xmlfile descriptor. Uses XMLPullParser so no memory is consumed for
        this task. '''

        for event, node in self.parser:
            if event == pulldom.START_ELEMENT and node.tagName in ('node', 'connector'):
                self.parser.expandNode(node)

                return node

        raise StopIteration

    def __iter__(self):
        return self

    def find(self, testfunc:Callable[[Element], bool]) -> Element:
        ''' Given an interator returned by the previous function, tries to find the
        first node matching the given condition '''
        for element in self:
            if testfunc(element):
                return element

        raise ElementNotFound('node or edge matching the given condition was not found')

def get_ref(el:Element):
    if el.getAttribute('id'):
        return '#' + el.getAttribute('id')
    elif el.getAttribute('class'):
        return '.' + el.getAttribute('class')

    return None

@comment
def etree_from_list(root:Element, nodes:[Element]) -> 'ElementTree':
    ''' Returns a built ElementTree from the list of its members '''
    root = Element(root.tag, attrib=root.attrib)
    root.extend(nodes)

    return ElementTree(root)

@comment
def nodes_from(node:Element, graph):
    ''' returns an iterator over the (node, edge)s that can be reached from
    node '''
    for edge in graph.findall(".//*[@from='{}']".format(node.attrib['id'])):
        yield (graph.find(".//*[@id='{}']".format(edge.attrib['to'])), edge)

@comment
def has_no_incoming(node:Element, graph:'root Element'):
    ''' returns true if this node has no edges pointing to it '''
    return len(graph.findall(".//*[@to='{}']".format(node.attrib['id']))) == 0

@comment
def has_edges(graph:'root Element'):
    ''' returns true if the graph still has edge elements '''
    return len(graph.findall("./connector")) > 0

@comment
def topological_sort(start_node:Element, graph:'root Element') -> 'ElementTree':
    ''' sorts topologically the given xml element tree, source:
    https://en.wikipedia.org/wiki/Topological_sorting '''
    sorted_elements = [] # sorted_elements ← Empty list that will contain the sorted elements
    no_incoming = [(start_node, None)] # (node, edge that points to this node)

    while len(no_incoming) > 0:
        node, edge = no_incoming.pop()

        if edge is not None:
            sorted_elements.append(edge)
        sorted_elements.append(node)

        for m, edge in nodes_from(node, graph=graph):
            graph.remove(edge)

            if has_no_incoming(m, graph):
                no_incoming.append((m, edge))

    if has_edges(graph) > 0:
        raise Exception('graph is cyclic')

    return etree_from_list(graph, sorted_elements)
