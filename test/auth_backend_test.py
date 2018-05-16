from cacahuate.auth.hierarchy.backref import BackrefHierarchyProvider
from cacahuate.models import User


def test_backref_backend(config):
    user = User(identifier='juan').save()
    br = BackrefHierarchyProvider(config)

    users = br.find_users(identifier='juan')

    assert len(users) == 1

    user = users[0]

    assert isinstance(user, User)
    assert user.identifier == 'juan'
