class SortedMap:
    ''' Defines representation and serialization of a sorted map. It can be
    indexed by key or turned into a list '''

    def __init__(self, arg, *, key=None):
        self.items = {}
        self.item_order = []

        for item in arg:
            if callable(key):
                key_value = key(item)
            else:
                key_value = item[key]

            self.items[key_value] = item
            self.item_order.append(key_value)

    def to_json(self):
        return {
            '_type': ':sorted_map',
            'items': self.items,
            'item_order': self.item_order,
        }

    def __iter__(self):
        def iterator():
            for item in self.item_order:
                yield self.items[item]

        return iterator()

    def __getitem__(self, item):
        if type(item) == str:
            return self.items[item]

        if type(item) == int:
            return self.items[self.item_order[item]]


class Map:
    ''' a utility class for managing maps similar to SortedMap '''

    def __init__(self, arg, *, key=None):
        self.items = {}

        for item in arg:
            if callable(key):
                key_value = key(item)
            else:
                key_value = item[key]
            self.items[key_value] = item

    def to_json(self):
        return {
            '_type': ':map',
            'items': self.items,
        }

    def __iter__(self):
        return iter(self.items.values())

    def __getitem__(self, item):
        return self.items[item]
