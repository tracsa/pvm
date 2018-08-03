from cacahuate.auth.base import BaseHierarchyProvider


class BackrefHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        return [
            (params.get('identifier'), {
                'identifier': params.get('identifier'),
                'email': params.get('identifier'),
                'fullname': params.get('identifier'),
            }),
        ]
