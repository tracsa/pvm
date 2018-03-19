from typing import Iterator, TextIO, Callable
import os
import xml.etree.ElementTree as ET

from .errors import ProcessNotFound, ElementNotFound


class Xml:

    def __init__(self, config):
        self.config = config
        self.file = None
        self.name = None
        self.parser = ET.XMLPullParser(['end'])

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
                obj = Xml(config)

                obj.name = filename
                obj.file = open(os.path.join(config['XML_PATH'], filename))

                return obj
        else:
            raise ProcessNotFound('Could not find the requested process definition'
                ' file: {}'.format(common_name))

    def __next__(self):
        ''' Returns an inerator over the nodes and edges of a process defined
        by the xmlfile descriptor. Uses XMLPullParser so no memory is consumed for
        this task. '''

        for line in self.file:
            self.parser.feed(line)

            for _, elem in self.parser.read_events():
                if elem.tag in ('node', 'connector'):
                    return elem

        self.file.close()

        raise StopIteration

    def __iter__(self):
        return self

    def find(self, testfunc:Callable[[ET.Element], bool]) -> ET.Element:
        ''' Given an interator returned by the previous function, tries to find the
        first node matching the given condition '''
        for element in self:
            if testfunc(element):
                return element

        raise ElementNotFound('node or edge matching the given condition was not found')

def etree_from_list(root:ET.Element, nodes:[ET.Element]) -> ET.ElementTree:
    ''' Returns a built ElementTree from the list of its members '''
    root = ET.Element(root.tag, attrib=root.attrib)
    root.extend(nodes)

    return ET.ElementTree(root)

def nodes_from(node:ET.Element, graph):
    ''' returns an iterator over the (node, edge)s that can be reached from
    node '''
    for edge in graph.findall(".//*[@from='{}']".format(node.attrib['id'])):
        yield (graph.find(".//*[@id='{}']".format(edge.attrib['to'])), edge)

def has_no_incoming(node:ET.Element, graph:'root ET.Element'):
    ''' returns true if this node has no edges pointing to it '''
    return len(graph.findall(".//*[@to='{}']".format(node.attrib['id']))) == 0

def has_edges(graph:'root ET.Element'):
    ''' returns true if the graph still has edge elements '''
    return len(graph.findall("./connector")) > 0

def topological_sort(start_node:ET.Element, graph:'root ET.Element') -> ET.ElementTree:
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
