import xml.etree.ElementTree as ET
from typing import Iterator, TextIO, Callable
import os

from .errors import ProcessNotFound, ElementNotFound

def load(config, common_name:str) -> TextIO:
    ''' Loads an xml file and returns the corresponding TextIOWrapper for
    further usage. The file might contain multiple versions so the latest one
    is chosen.

    common_name is the prefix of the file to find. If multiple files with the
    same prefix are found the last in lexicographical order is returned.'''
    files = reversed(sorted(os.listdir(config['XML_PATH'])))

    for filename in files:
        if filename.startswith(common_name):
            return open(os.path.join(config['XML_PATH'], filename))
    else:
        raise ProcessNotFound('Could not find the requested process definition'
            ' file: {}'.format(common_name))

def iter_nodes(xmlfile:TextIO) -> Iterator[ET.Element]:
    ''' Returns an inerator over the nodes and edges of a process defined
    by the xmlfile descriptor. Uses XMLPullParser so no memory is consumed for
    this task. '''
    parser = ET.XMLPullParser(['end'])

    for line in xmlfile:
        parser.feed(line)

        for _, elem in parser.read_events():
            if elem.tag in ('node', 'connector'):
                yield elem

    xmlfile.close()

def find(xmliter:Iterator[ET.Element], testfunc:Callable[[ET.Element], bool]) -> ET.Element:
    ''' Given an interator returned by the previous function, tries to find the
    first node matching the given condition '''
    for element in xmliter:
        if testfunc(element):
            return element

    raise ElementNotFound('node or edge matching the given condition was not found')
