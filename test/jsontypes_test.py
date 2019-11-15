import pytest

from cacahuate.jsontypes import SortedMap, Map, MultiFormDict


def test_sorted_map():
    sm = SortedMap([
        {
            'id': '1',
            'name': 'la',
        },
        {
            'id': '2',
            'name': 'le',
        },
    ], key='id')

    assert sm.to_json() == {
        '_type': ':sorted_map',
        'items': {
            '1': {
                'id': '1',
                'name': 'la',
            },
            '2': {
                'id': '2',
                'name': 'le',
            },
        },
        'item_order': ['1', '2'],
    }

    assert list(sm) == [
        {
            'id': '1',
            'name': 'la',
        },
        {
            'id': '2',
            'name': 'le',
        },
    ]

    assert sm['2'] == {
        'id': '2',
        'name': 'le',
    }

    assert sm[0] == {
        'id': '1',
        'name': 'la',
    }


def test_sorted_map_function_key():
    sm = SortedMap([
        {
            'name': 'la',
            'sub': {
                'id': '1',
            },
        },
        {
            'name': 'le',
            'sub': {
                'id': '2',
            },
        },
    ], key=lambda x: x['sub']['id'])

    assert sm.item_order == ['1', '2']
    assert sm.items == {
        '1': {
            'name': 'la',
            'sub': {
                'id': '1',
            },
        },
        '2': {
            'name': 'le',
            'sub': {
                'id': '2',
            },
        },
    }


def test_map():
    sm = Map([
        {
            'id': '1',
            'name': 'la',
        },
        {
            'id': '2',
            'name': 'le',
        },
    ], key='id')

    assert sm.to_json() == {
        '_type': ':map',
        'items': {
            '1': {
                'id': '1',
                'name': 'la',
            },
            '2': {
                'id': '2',
                'name': 'le',
            },
        },
    }

    assert sorted(list(sm), key=lambda x: x['id']) == [
        {
            'id': '1',
            'name': 'la',
        },
        {
            'id': '2',
            'name': 'le',
        },
    ]

    assert sm['2'] == {
        'id': '2',
        'name': 'le',
    }


def test_multivalued_map():
    ulist = [
        {
            'a': 'a',
            'b': 1,
        },
        {
            'b': 2,
        },
        {
            'a': 'b',
            'b': 3,
        },
    ]
    mv = MultiFormDict(ulist)

    # by default last value is used
    assert mv['b'] == 3

    with pytest.raises(KeyError):
        mv['da']

    assert mv.get('b') == 3
    assert mv.get('c', 40) == 40

    assert mv.getlist('b') == [1, 2, 3]
    assert mv.getlist('a', 'c') == ['a', 'c', 'b']

    assert list(mv.all()) == ulist
    assert list(mv.items()) == [('a', 'b'), ('b', 3)]
    assert list(mv.values()) == ['b', 3]
    assert list(mv.keys()) == ['a', 'b']

    assert mv.dict() == {
        'a': 'b',
        'b': 3,
    }
