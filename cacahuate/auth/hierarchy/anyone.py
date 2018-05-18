from cacahuate.auth.base import BaseHierarchyProvider


class AnyoneHierarchyProvider(BaseHierarchyProvider):

    def validate_user(self, user, **params):
        pass
