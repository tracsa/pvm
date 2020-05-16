from base64 import b64encode
from cacahuate.models import Execution, Pointer, User, Token
from random import choice
from string import ascii_letters
from datetime import datetime


def random_string(length=6):
    return ''.join(choice(ascii_letters) for _ in range(6))


def make_user(identifier, name, email=None):
    u = User(identifier=identifier, fullname=name, email=email).save()
    token = Token(
        token=random_string(9)
    ).save()
    token.proxy.user.set(u)

    return u


def make_auth(user):
    return {
        'Authorization': 'Basic {}'.format(
            b64encode(
                '{}:{}'.format(
                    user.identifier,
                    user.proxy.tokens.get()[0].token,
                ).encode()
            ).decode()
        ),
    }


def make_pointer(process_name, node_id):
    exc = Execution(
        process_name=process_name,
    ).save()
    ptr = Pointer(
        node_id=node_id,
    ).save()
    ptr.proxy.execution.set(exc)

    return ptr


def make_date(year=2018, month=5, day=4, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second)


def assert_near_date(date, seconds=2):
    assert (date - datetime.now()).total_seconds() < seconds
