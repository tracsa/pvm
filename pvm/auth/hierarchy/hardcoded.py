from pvm.auth.base import BaseHierarchyProvider
from pvm.auth.backends.hardcoded import HardcodedUser
from pvm.errors import HierarchyError
from pvm.models import User


class HardcodedHierarchyProvider(BaseHierarchyProvider):

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

        return list(map(
            lambda u: HardcodedUser(username=u.identifier),
            User.q().filter(
                identifier='{}_{}'.format(employee, relation)
            )
        ))
