from base64 import b64encode
from cacahuate.models import Execution, Pointer, User, Token, Activity
from random import choice
from string import ascii_letters


def make_user(identifier, name):
    u = User(identifier=identifier, human_name=name).save()
    token = Token(
        token=''.join(choice(ascii_letters) for c in range(9))
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


def make_activity(ref, user, execution):
    act = Activity(ref=ref).save()
    act.proxy.user.set(user)
    act.proxy.execution.set(execution)

    return act
