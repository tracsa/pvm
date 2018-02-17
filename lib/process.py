import xml.etree.ElementTree as ET
import os

from .errors import ProcessNotFound

def load(config, common_name:str) -> ET.ElementTree:
    files = reversed(sorted(os.listdir(config['XML_PATH'])))

    for filename in files:
        if filename.startswith(common_name):
            return ET.parse(os.path.join(config['XML_PATH'], filename))

    raise ProcessNotFound('Could not find the requested process definition file')
