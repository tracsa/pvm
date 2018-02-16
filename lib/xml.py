import xml.etree.ElementTree as ET

def get_nodes_and_edges(xmlfile: 'file descriptor') -> (['nodes'], ['edges']):
    ''' given a file descriptor that points to a XML file return a tuple that
    contains as first element the nodes of the xml, and as second element the
    edges '''
    parser = ET.XMLPullParser(['end'])
    nodes, edges = [], []

    for line in xmlfile:
        parser.feed(line)

        for event, elem in parser.read_events():
            if elem.tag == 'node':
                nodes.append(elem)
            elif elem.tag == 'connector':
                edges.append(elem)

    return nodes, edges

def etree_from_list(config:dict, nodes:[ET.Element]) -> ET.ElementTree:
    ''' Returns a built ElementTree from the list of its members '''
    tb = ET.TreeBuilder()
    root = tb.start(config['PROCESS_ELEMENT'], dict())

    root.extend(nodes)

    tb.end(config['PROCESS_ELEMENT'])

    return ET.ElementTree(tb.close())

def topological_sort(nodes:[ET.Element], edges:[ET.Element]) -> ET.ElementTree:
    ''' sorts topologically the given xml element tree, source:
    https://en.wikipedia.org/wiki/Topological_sorting '''
    sorted_elements = [] # L ← Empty list that will contain the sorted elements
    # S ← Set of all nodes with no incoming edge
    # while S is non-empty do
        # remove a node n from S
        # add n to tail of L
        # for each node m with an edge e from n to m do
            # remove edge e from the graph
            # if m has no other incoming edges then
                # insert m into S
    # if graph has edges then
        # return error (graph has at least one cycle)
    # else
        # return L (a topologically sorted order)
    return etree_from_list(sorted_elements)

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
