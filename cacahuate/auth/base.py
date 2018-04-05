from cacahuate.models import User


class BaseUser:

    def get_user(self):
        identifier = self.get_identifier()

        # fetchs redis mirror user if there is None then creates one
        user = User.get_by('identifier', identifier)

        if user is None:
            user = User(identifier=identifier).save()

        return user

    def get_identifier(self):
        raise NotImplementedError('Must be implemented in subclasses')

    def get_human_name(self):
        raise NotImplementedError('Must be implemented in subclasses')

    def get_x_info(self, notification_backend):
        raise NotImplementedError('Must be implemented in subclasses')


class BaseAuthProvider:

    def __init__(self, config):
        self.config = config

    def authenticate(self, **credentials) -> BaseUser:
        raise NotImplementedError('Must be implemented in subclasses')


class BaseHierarchyProvider:

    def __init__(self, config):
        self.config = config

    def validate_user(self, user, **params):
        ''' given a user, should rise an exception if the user does not match
        the hierarchy conditions required via params '''
        raise NotImplementedError('Must be implemented in subclasses')

    def find_users(self, **params) -> [BaseUser]:
        ''' given the params, retrieves the
        user identifiers that match them '''
        raise NotImplementedError('Must be implemented in subclasses')
