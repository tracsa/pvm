from cacahuate.auth.base import BaseHierarchyProvider, BaseUser
from cacahuate.auth.backends.hardcoded import HardcodedUser
from cacahuate.errors import HierarchyError
from cacahuate.models import User


class Self(BaseUser):
    """docstring for Self"""

    def __init__(self, identifier):
        self.identifier = identifier

    def get_identifier(self):
        return self.identifier

    def get_x_info(self, medium):
        return "hardcoded@mailinator.com"


class SelfHierarchyProvider(BaseHierarchyProvider):

    def validate_user(self, user, **params):
        base_user = User.get_by('identifier', params.get('employee'))

        if base_user is None:
            raise HierarchyError

        relation = params.get('relation')
        manager_identifier = '{}_{}'.format(base_user.identifier, relation)
        manager = User.get_by('identifier', manager_identifier)

        if manager is None or manager.id != user.id:
            raise HierarchyError

    def find_users(self, **params):
        employee = params.get('employee')
        relation = params.get('relation')

        return [Self(params.get('identifier'))]
