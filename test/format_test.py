from flask import json

from cacahuate.models import Execution

from .utils import make_auth, make_user


def test_interpolated_name(config, client, mongo):
    juan = make_user('juan', 'Juan')
    name = 'Computes a name based on a Cow'

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'interpol',
        'form_array': [{
            'ref': 'form',
            'data': {
                'field': 'Cow',
            },
        }],
    }))

    # request succeeded
    assert res.status_code == 201

    # execution has name
    exc = Execution.get_all()[0]

    assert exc.name == name

    # execution collection has name
    reg2 = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg2['id'] == exc.id
    assert reg2['name'] == name

    # history has the name
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert reg['execution']['name'] == name


def test_interpolate_everything(config, client, mongo):
    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'interpolception',
        'form_array': [{
            'ref': 'form',
            'data': {
                'field': 'Magic',
            },
        }],
    }))

    # request succeeded
    assert res.status_code == 201

    # execution has name
    exc = Execution.get_all()[0]

    assert exc.name == 'Name Magic'
    assert exc.description == 'Description Magic'

    # execution collection has name
    reg2 = next(mongo[config["EXECUTION_COLLECTION"]].find())

    assert reg2['id'] == exc.id
    assert reg2['name'] == 'Name Magic'
    assert reg2['description'] == 'Description Magic'

    # history has the name
    reg = next(mongo[config["POINTER_COLLECTION"]].find())

    assert reg['execution']['name'] == 'Name Magic'
    assert reg['execution']['description'] == 'Description Magic'
