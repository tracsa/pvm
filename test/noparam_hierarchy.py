from cacahuate.auth.base import BaseHierarchyProvider


class NoparamHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        return [('foo', {
            'identifier': 'foo',
        })]
