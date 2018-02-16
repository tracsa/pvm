import xml.etree.ElementTree as ET

def etree_from_list(root:ET.Element, nodes:[ET.Element]) -> ET.ElementTree:
    ''' Returns a built ElementTree from the list of its members '''
    root = ET.Element(root.tag, attrib=root.attrib)
    root.extend(nodes)

    return ET.ElementTree(root)

def nodes_from(node:ET.Element, graph):
    for edge in graph.findall(".//*[@from='{}']".format(node.attrib['id'])):
        yield (graph.find(".//*[@id='{}']".format(edge.attrib['to'])), edge)

def topological_sort(start_node:ET.Element, graph:ET.Element) -> ET.ElementTree:
    ''' sorts topologically the given xml element tree, source:
    https://en.wikipedia.org/wiki/Topological_sorting '''
    sorted_elements = [] # sorted_elements ← Empty list that will contain the sorted elements
    no_incoming = [start_node]

    while len(no_incoming) > 0:
        node = no_incoming.pop()
        sorted_elements.append(node)

        for m, edge in nodes_from(node, graph=graph):
            graph.remove(e)

            if has_no_incoming(m, graph):
                no_incoming.append(m)

    if has_edges(graph) > 0:
        raise Exception('graph is cyclic')

    return etree_from_list(graph, sorted_elements)

class XML:

    def __init__(self, config: dict):
        self.config = config

    def find_next_element(xmlname: str, elem_id: str):
        ''' finds an element pointed by an arrow by current's element id,
        if this is an end node return None. If this is a parallel execution node
        returns an array of the pointed elements.'''
        parser = ET.XMLPullParser(['end'])

        with open(xmlname) as xmlfile:
            for line in xmlfile:
                parser.feed(line)

                for _, elem in parser.read_events():
                    if 'id' in elem.attrib:
                        print(elem, elem.attrib)
