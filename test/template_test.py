from flask import json
import pika

from cacahuate.models import Execution

from .utils import make_auth, make_user

EXECUTION_ID = '15asbs'


def test_render_execution_summary(client, mocker):
    # Create process
    mocker.patch(
        'pika.adapters.blocking_connection.'
        'BlockingChannel.basic_publish'
    )

    juan = make_user('juan', 'Juan')

    res = client.post('/v1/execution', headers={**{
        'Content-Type': 'application/json',
    }, **make_auth(juan)}, data=json.dumps({
        'process_name': 'simple',
        'form_array': [{
            'ref': 'start_node',
            'data': {
                'data': 'here',
            },
        }],
    }))

    assert res.status_code == 201

    exc = Execution.get_all()[0]

    # Fetch process summary
    res = client.get('/v1/execution/{}/summary'.format(exc.id))

    assert res.status_code == 200
