from cacahuate.auth.base import BaseHierarchyProvider


class HardcodedHierarchyProvider(BaseHierarchyProvider):

    def find_users(self, **params):
        employee = params.get('identifier')
        relation = params.get('relation')

        new_identifier = '{}_{}'.format(employee, relation)

        return [
            (new_identifier, {
                'identifier': new_identifier,
            })
        ]
