from cacahuate.auth.base import BaseHierarchyProvider
from cacahuate.errors import HierarchyError
from cacahuate.models import User


class BadreturnHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        if params.get('opt') == 'return':
            return None

        elif params.get('opt') == 'item':
            return [None]
