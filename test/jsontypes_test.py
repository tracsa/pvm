from cacahuate.jsontypes import SortedMap, Map, MultiValueMap


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
    mv = MultiValueMap({
        'a': [1, 2, 3],
        'b': [4],
    })

    # by default last value is used
    assert mv['a'] == 3
    assert mv['b'] == 4

    # values can be iterated
    values = [1, 2, 3]
    for i, v  in enumerate(mv.getlist('a')):
        assert v == values[i]
