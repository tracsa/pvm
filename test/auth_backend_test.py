from cacahuate.auth.hierarchy.backref import BackrefHierarchyProvider
from cacahuate.auth.base import BaseUser

def test_backref_backend(config):
    br = BackrefHierarchyProvider(config)

    users = br.find_users(identifier='juan')

    assert len(users) == 1

    user = users[0]

    assert isinstance(user, BaseUser)
    assert user.get_identifier() == 'juan'
