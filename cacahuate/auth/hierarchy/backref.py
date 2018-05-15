from cacahuate.auth.base import BaseHierarchyProvider
from cacahuate.models import User


class BackrefHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        return [User.get_by('identifier', params.get('identifier'))]
