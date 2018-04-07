from cacahuate.auth.base import BaseHierarchyProvider
from cacahuate.auth.backends.hardcoded import HardcodedUser
from cacahuate.errors import HierarchyError
from cacahuate.models import User


class HardcodedHierarchyProvider(BaseHierarchyProvider):

    def validate_user(self, user, **params):
        base_user = User.get_by('identifier', params.get('identifier'))

        if base_user is None:
            raise HierarchyError

        relation = params.get('relation')
        manager_identifier = '{}_{}'.format(base_user.identifier, relation)
        manager = User.get_by('identifier', manager_identifier)

        if manager is None or manager.id != user.id:
            raise HierarchyError

    def find_users(self, **params):
        employee = params.get('identifier')
        relation = params.get('relation')

        return list(map(
            lambda u: HardcodedUser(username=u.identifier),
            User.q().filter(
                identifier='{}_{}'.format(employee, relation)
            )
        ))
