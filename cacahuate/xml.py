from typing import Iterator, TextIO, Callable
import os
from xml.dom import pulldom
from xml.dom.minidom import Element

from .errors import ProcessNotFound, ElementNotFound, MalformedProcess
from .mark import comment

XML_ATTRIBUTES = {
    'public': lambda a: a == 'true',
    'author': str,
    'date': str,
    'name': str,
    'description': lambda x: x,
    'start-node': lambda x: x,
}


class Xml:

    def __init__(self, config, filename):
        try:
            self.id, self.version, _ = filename.split('.')
        except ValueError:
            raise MalformedProcess(
                'Name of process is invalid, must be name.version.xml'
            )

        self.versions = [self.version]
        self.filename = filename
        self.config = config
        self.parser = pulldom.parse(
            open(os.path.join(config['XML_PATH'], filename))
        )

        try:
            info_node = next(self)
        except StopIteration:
            raise MalformedProcess('This process lacks the process-info node')

        if info_node.tagName != 'process-info':
            raise MalformedProcess('process-info node must be the first node')

        for attr, func in XML_ATTRIBUTES.items():
            try:
                node = info_node.getElementsByTagName(attr)[0]
            except IndexError:
                raise MalformedProcess(
                    'Process\' metadata lacks node {}'.format(attr)
                )

            if node.firstChild is not None:
                node.normalize()
                setattr(self, attr, func(node.firstChild.nodeValue))
            else:
                # the text child of <element></element> is the empty string
                setattr(self, attr, func(''))

    @classmethod
    def load(cls, config: dict, common_name: str, direct=False) -> TextIO:
        ''' Loads an xml file and returns the corresponding TextIOWrapper for
        further usage. The file might contain multiple versions so the latest
        one is chosen.

        common_name is the prefix of the file to find. If multiple files with
        the same prefix are found the last in lexicographical order is
        returned.'''
        if direct:
            # skip looking for the most recent version
            return Xml(config, common_name)

        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        for filename in files:
            if filename.startswith(common_name):
                return Xml(config, filename)
        else:
            raise ProcessNotFound(common_name)

    def __next__(self):
        ''' Returns an inerator over the nodes and edges of a process defined
        by the xmlfile descriptor. Uses XMLPullParser so no memory is consumed
        for this task. '''

        ITERABLES = ('node', 'connector', 'process-info')

        for event, node in self.parser:
            if event == pulldom.START_ELEMENT and node.tagName in ITERABLES:
                self.parser.expandNode(node)

                return node

        raise StopIteration

    def __iter__(self):
        return self

    def find(self, testfunc: Callable[[Element], bool]) -> Element:
        ''' Given an interator returned by the previous function, tries to find
        the first node matching the given condition '''
        for element in self:
            if testfunc(element):
                return element

        raise ElementNotFound(
            'node or edge matching the given condition was not found'
        )

    def start_node(self) -> Element:
        ''' Returns the starting node '''
        start_node_id = getattr(self, 'start-node')
        start_node = self.find(lambda e: e.getAttribute('id') == start_node_id)

        return start_node

    @classmethod
    def list(cls, config):
        # Get all processes
        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        # Load only the oldest processes
        processes = []

        for filename in files:
            try:
                id, version, _ = filename.split('.')
            except ValueError:
                continue

            try:
                xml = cls.load(config, filename, direct=True)
            except ProcessNotFound:
                continue
            except MalformedProcess:
                continue

            if not xml.public:
                continue

            if len(processes) == 0 or processes[-1].id != id:
                processes.append(xml)
            else:
                processes[-1].versions.append(version)

        return processes

    def to_json(self):
        return {
            'id': self.id,
            'version': self.version,
            'author': self.author,
            'date': self.date,
            'name': self.name,
            'description': self.description,
            'versions': self.versions,
        }


def get_ref(el: Element):
    if el.getAttribute('id'):
        return '#' + el.getAttribute('id')
    elif el.getAttribute('class'):
        return '.' + el.getAttribute('class')

    return None


def resolve_params(filter_node, execution=None):
    computed_params = {}

    for param in filter_node.getElementsByTagName('param'):
        if execution is not None and param.getAttribute('type') == 'ref':
            user_ref = param.firstChild.nodeValue.split('#')[1].strip()

            try:
                actor = next(
                    execution.proxy.actors.q().filter(ref='#'+user_ref)
                )

                value = actor.proxy.user.get().identifier
            except StopIteration:
                value = None
        else:
            value = param.firstChild.nodeValue

        computed_params[param.getAttribute('name')] = value

    return computed_params


@comment
def etree_from_list(root: Element, nodes: [Element]) -> 'ElementTree':
    ''' Returns a built ElementTree from the list of its members '''
    root = Element(root.tag, attrib=root.attrib)
    root.extend(nodes)

    return ElementTree(root)


@comment
def nodes_from(node: Element, graph):
    ''' returns an iterator over the (node, edge)s that can be reached from
    node '''
    for edge in graph.findall(".//*[@from='{}']".format(node.attrib['id'])):
        yield (graph.find(".//*[@id='{}']".format(edge.attrib['to'])), edge)


@comment
def has_no_incoming(node: Element, graph: 'root Element'):
    ''' returns true if this node has no edges pointing to it '''
    return len(graph.findall(".//*[@to='{}']".format(node.attrib['id']))) == 0


@comment
def has_edges(graph: 'root Element'):
    ''' returns true if the graph still has edge elements '''
    return len(graph.findall("./connector")) > 0


@comment
def topological_sort(start_node: Element, graph: 'Element') -> 'ElementTree':
    ''' sorts topologically the given xml element tree, source:
    https://en.wikipedia.org/wiki/Topological_sorting '''
    sorted_elements = []  # Empty list that will contain the sorted elements
    no_incoming = [(start_node, None)]  # (node, edge that points to this node)

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


SUPPORTED_ATTRS = {
    'type': str,
    'name': str,
    'required': lambda x: bool(x),
    'regex': str,
    'label': str,
    'placeholder': str,
    'default': str,
    'helper': str,
}


def form_to_dict(form):
    inputs = form.getElementsByTagName('input')

    form_dict = {
        'ref': get_ref(form),
        'inputs': [],
    }

    for input in inputs:
        input_attrs = [
            (attr, func(input.getAttribute(attr)))
            for attr, func in SUPPORTED_ATTRS.items()
        ] + [('options', list(map(
            lambda e: {
                'value': e.getAttribute('value'),
                'label': e.firstChild.nodeValue,
            },
            input.getElementsByTagName('option'),
        )))]

        form_dict['inputs'].append(dict(filter(
            lambda a: a[1],
            input_attrs
        )))

    return form_dict
