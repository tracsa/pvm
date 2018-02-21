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

def test_load_specific_version():
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

def test_make_iterator():
    ''' test that the iter function actually returns an interator over the
    nodes and edges of the process '''
    config = get_testing_config()
    xmliter = lib.process.iter_nodes(lib.process.load(config, 'simple'))

    expected_nodes = [
        ET.Element('node', {'id':"gYcj0XjbgjSO", 'class':"start"}),
        ET.Element('connector', {'from':"gYcj0XjbgjSO", 'to':"4g9lOdPKmRUf"}),
        ET.Element('node', {'id':"4g9lOdPKmRUf", 'class':"echo"}),
        ET.Element('connector', {'from':"4g9lOdPKmRUf", 'to':"kV9UWSeA89IZ"}),
        ET.Element('node', {'id':"kV9UWSeA89IZ", 'class':"end"}),
    ]

    for given, expected in zip(xmliter, expected_nodes):
        assert given.tag == expected.tag
        assert given.attrib == expected.attrib

def test_find():
    config = get_testing_config()
    xmliter = lib.process.iter_nodes(lib.process.load(config, 'simple'))

    start = lib.process.find(xmliter, lambda e:e.tag=='node')

    assert start.tag == 'node'
    assert start.attrib['id'] == 'gYcj0XjbgjSO'

    conn = lib.process.find(
        xmliter,
        lambda e:e.tag=='connector' and e.attrib['from']==start.attrib['id']
    )

    assert conn.tag == 'connector'
    assert conn.attrib == { 'from':"gYcj0XjbgjSO", 'to':"4g9lOdPKmRUf" }

    echo = lib.process.find(
        xmliter,
        lambda e:e.attrib['id']==conn.attrib['to']
    )

    assert echo.tag == 'node'
    assert echo.attrib['id'] == '4g9lOdPKmRUf'

    conn = lib.process.find(
        xmliter,
        lambda e:e.tag=='connector' and e.attrib['from']==echo.attrib['id']
    )

    assert conn.tag == 'connector'
    assert conn.attrib == {'from':"4g9lOdPKmRUf", 'to':"kV9UWSeA89IZ"}

    end = lib.process.find(
        xmliter,
        lambda e:e.attrib['id']==conn.attrib['to']
    )

    assert end.tag == 'node'
    assert end.attrib['id'] == 'kV9UWSeA89IZ'
