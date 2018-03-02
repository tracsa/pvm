class ProcessNotFound(Exception): pass

class ElementNotFound(Exception): pass

class CannotMove(Exception): pass

class DataMissing(CannotMove):

    def __init__(self, key):
        super().__init__('missing data: {}'.format(key))

class InvalidData(CannotMove):

    def __init__(self, key, value):
        super().__init__('invalid data for key {}: {}'.format(key, value))
