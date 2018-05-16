class SortedMap:
    ''' Defines representation and serialization of a sorted map. It can be
    indexed by key or turned into a list '''

    def __init__(self, arg, *, key=None):
        self.items = {}
        self.item_order = []

        for item in arg:
            self.items[item[key]] = item
            self.item_order.append(item[key])

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
