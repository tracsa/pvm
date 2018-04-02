class BaseUser:

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
