import pytest
import xml.etree.ElementTree as ET
from io import TextIOWrapper

from .context import lib, get_testing_config

def test_load_not_found():
    ''' if a process file is not found, raise an exception '''
    config = get_testing_config()

    with pytest.raises(lib.errors.ProcessNotFound):
        lib.process.load(config, 'notfound')

def test_load_process():
    '''  a process file can be found using only its prefix or common name '''
    config = get_testing_config()
    xmlfile = lib.process.load(config, 'simple')

    assert type(xmlfile) == TextIOWrapper

def test_load_last_matching_process():
    ''' a process is specified by its common name, but many versions may exist.
    when a process is requested for start we must use the last version of it '''
    config = get_testing_config()
    xmlfile = lib.process.load(config, 'oldest')

    root = ET.fromstring(xmlfile.read())

    assert root.tag == 'process-spec'
    assert root[0].tag == 'process-info'
    assert root[0][0].tag == 'author'
    assert root[0][0].text == 'categulario'
    assert root[0][1].tag == 'date'
    assert root[0][1].text == '2018-02-17'
    assert root[0][2].tag == 'name'
    assert root[0][2].text == 'Oldest process v2'
    assert root[1].tag == 'process'

def test_can_pick_specific_version():
    ''' one should be able to request a specific version of a process,
    thus overriding the process described by the previous test '''
    config = get_testing_config()
    xmlfile = lib.process.load(config, 'oldest_2018-02-14')

    root = ET.fromstring(xmlfile.read())

    assert root.tag == 'process-spec'
    assert root[0].tag == 'process-info'
    assert root[0][0].tag == 'author'
    assert root[0][0].text == 'categulario'
    assert root[0][1].tag == 'date'
    assert root[0][1].text == '2018-02-14'
    assert root[0][2].tag == 'name'
    assert root[0][2].text == 'Oldest process'
    assert root[1].tag == 'process'
