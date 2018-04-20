from cacahuate.auth.base import BaseHierarchyProvider, BaseUser


class User(BaseUser):
    def __init__(self, identifier):
        self.identifier = identifier

    def get_identifier(self):
        return self.identifier


class BackrefHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        return [User(params.get('identifier'))]
