''' Helper structures that take data from a json representation and create an
object with specific behaviour '''


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
    ''' a utility class for managing maps similar to SortedMap, some logic
    borrowed from django's QueryDict '''

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


class MultiFormDict:
    """
    A special dictionary that can take values from a list of dictionaries
    that share the keys, by default returns the value of the last one
    """
    def __init__(self, dict_list):
        self.dict_list = dict_list

    def __repr__(self):
        return repr(self.dict_list)

    def __getitem__(self, key):
        """
        Return the last data value for this key, or [] if it's an empty list;
        raise KeyError if not found.
        """
        if len(self.dict_list) == 0:
            raise KeyError(key)

        return self.dict_list[-1][key]

    def get(self, key, default=None):
        """
        Return the last data value for the passed key. If key doesn't exist
        or value is an empty list, return `default`.
        """
        if len(self.dict_list) == 0:
            return default

        try:
            return self.dict_list[-1][key]
        except KeyError:
            return default

    def getlist(self, key, default=None):
        ''' return a list of values for this key where every missing key of an
        underlaying dict is replaced by `default` '''
        if len(self.dict_list) == 0:
            return []

        return [d.get(key, default) for d in self.dict_list]

    def list(self):
        """
        Return a list of values for the key.

        Used internally to manipulate values list. If force_list is True,
        return a new copy of values.
        """
        return self.dict_list[:]

    def items(self):
        """
        Yield (key, value) pairs, where value is the last item in the list
        associated with the key.
        """
        if len(self.dict_list) == 0:
            return None

        return self.dict_list[-1].items()

    def values(self):
        """Yield the last value on every key list."""
        if len(self.dict_list) == 0:
            return None

        return self.dict_list[-1].values()

    def keys(self):
        """Yield the last value on every key list."""
        if len(self.dict_list) == 0:
            return None

        return self.dict_list[-1].keys()

    def dict(self):
        """Return current object as a dict with singular values."""
        try:
            return self.dict_list[-1].copy()
        except IndexError:
            return {}
