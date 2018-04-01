class BaseHierarchyProvider:

    def __init__(self, config):
        self.config = config

    def validate_user(self, user, **params):
        ''' given a user, should rise an exception if the user does not match
        the hierarchy conditions required via params '''
        raise NotImplementedError('Must be implemented in subclasses')

    def find_users(self, **params):
        ''' given the params, retrieves the user identifiers that match them '''
        raise NotImplementedError('Must be implemented in subclasses')
