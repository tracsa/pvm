class BaseAuthProvider:

    def __init__(self, config):
        self.config = config

    def authenticate(self, **credentials):
        ''' validates credentials and returns an user in the format:
        ('identifier', {data}) or raises an exception like AuthFieldInvalid or
        AuthFieldRequired'''
        raise NotImplementedError('Must be implemented in subclasses')


class BaseHierarchyProvider:

    def __init__(self, config):
        self.config = config

    def validate_user(self, user, **params):
        ''' given a user, should rise an exception if the user does not match
        the hierarchy conditions required via params, it is only useful for
        the first node of a process '''
        raise NotImplementedError('Must be implemented in subclasses')

    def find_users(self, **params):
        ''' given the params, retrieves the user identifiers that match them in
        the format: ('identifier', {data}). '''
        raise NotImplementedError('Must be implemented in subclasses')
