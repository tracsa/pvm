import xml.etree.ElementTree as ET

class XML:

    def __init__(self, config):
        self.config = config

    def find_next_element(xmlname, elem_id):
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
