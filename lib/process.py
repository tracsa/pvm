import xml.etree.ElementTree as ET
from typing import Iterator, TextIO
import os

from .errors import ProcessNotFound

def load(config, common_name:str) -> TextIO:
    files = reversed(sorted(os.listdir(config['XML_PATH'])))

    for filename in files:
        if filename.startswith(common_name):
            return open(os.path.join(config['XML_PATH'], filename))
    else:
        raise ProcessNotFound('Could not find the requested process definition'
            ' file: {}'.format(common_name))

def iter_nodes(xmlfile:TextIO) -> Iterator[ET.Element]:
    parser = ET.XMLPullParser(['end'])

    for line in xmlfile:
        parser.feed(line)

        for _, elem in parser.read_events():
            if elem.tag in ('node', 'connector'):
                yield elem

    xmlfile.close()
