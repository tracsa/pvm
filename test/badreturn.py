from cacahuate.auth.base import BaseHierarchyProvider


class BadreturnHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        if params.get('opt') == 'return':
            return None

        elif params.get('opt') == 'item':
            return [None]
