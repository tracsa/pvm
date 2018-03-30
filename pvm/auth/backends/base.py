class BaseAuthProvider:

    def __init__(self, config):
        self.config = config

    def authenticate(self, credentials={}):
        raise NotImplementedError('Must be implemented in subclasses')
