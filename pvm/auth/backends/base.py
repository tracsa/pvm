class BaseAuthProvider:

    def __init__(self, config):
        self.config = config

    def authenticate(self, username=None, password=None):
        raise NotImplementedError('Must be implemented in subclasses')
