from datetime import datetime

EXECUTION_ID = '15asbs'


def test_execution_summary_default_template(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'some-random-process.2018-04-04.xml',
            'values': {
                '_execution': [{
                    'name': 'My process',
                    'id': 'some id',
                    'process_name': 'some-random-process.2020-09-29.xml',
                    'description': 'some description',
                    'started_at': datetime(2020, 9, 29),
                }],
                'auth_form': [
                    {
                        'name': 'Jorge Juan',
                        'elections': 'amlo',
                    },
                ],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '''<!DOCTYPE html>
<html>
  <head>
    <title>Proceso - My process</title>
  </head>
  <body>
    <h1>My process</h1>
    <table>
      <tr>
        <th>ID</th>
        <td>some id</td>
      </tr>
      <tr>
        <th>Nombre</th>
        <td>My process</td>
      </tr>
      <tr>
        <th>Fuente</th>
        <td>some-random-process.2020-09-29.xml</td>
      </tr>
      <tr>
        <th>Descripción</th>
        <td>some description</td>
      </tr>
      <tr>
        <th>Inicio</th>
        <td>2020-09-29 00:00:00+00:00</td>
      </tr>
    </table>
  </body>
</html>'''

    assert expected == res.data.decode('utf8')


def test_execution_summary_version_level(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'version-level-template.2020-09-29.xml',
            'values': {
                '_execution': {
                },
                'auth_form': [
                    {
                        'name': 'Jorge Juan',
                        'elections': 'amlo',
                    },
                ],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = b'''<p>The form was filled by <b>Jorge Juan</b></p>
<p>He/She is voting for <b>amlo</b></p>'''

    assert expected == res.data


def test_execution_summary_process_level(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'process-level-template.2018-02-19.xml',
            'values': {
                '_execution': {
                },
                'start_form': [
                    {
                        'data': 'Foo',
                    },
                ],
                'mid_form': [
                    {
                        'data': 'Bar',
                    },
                ],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '\n'.join([
        '<p>start_form: Foo</p>',
        '<p>mid_node: Bar</p>',
        '<p>start_form and mid_form: "Foo" and "Bar"</p>',
    ])

    assert expected == res.data.decode("utf-8")


def test_execution_summary_template_overides1(client, mongo, config):
    # use version-overriden template
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'template-overrides.2020-09-29.xml',
            'values': {
                '_execution': {
                },
                'start_form': [
                    {
                        'data': 'Foo',
                    },
                ],
                'mid_form': [
                    {
                        'data': 'Bar',
                    },
                ],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '''version level template

General block
Version level custom block'''

    assert expected == res.data.decode("utf-8")


def test_execution_summary_template_overides2(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'template-overrides.2020-09-30.xml',
            'values': {
                '_execution': {
                },
                'start_form': [
                    {
                        'data': 'Foo',
                    },
                ],
                'mid_form': [
                    {
                        'data': 'Bar',
                    },
                ],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '''process level template

General block
Process level custom block'''

    assert expected == res.data.decode("utf-8")


def test_builtin_filter_datetimeformat(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'test-filter-date.2020-09-30.xml',
            'values': {
                '_execution': [{
                    'started_at': datetime(2020, 9, 30, 16, 31, 15),
                }],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '''ISO: 2020-09-30 16:31:15+0000
es_MX: 30/09/2020 16:31'''

    assert expected == res.data.decode("utf-8")


def test_custom_filter(client, mongo, config):
    mongo[config["EXECUTION_COLLECTION"]].insert_many([
        {
            'id': EXECUTION_ID,
            'process_name': 'test-custom-filter.2020-09-30.xml',
            'values': {
                '_execution': [{
                    'started_at': datetime(2020, 5, 10, 16, 31, 15),
                }],
            },
        },
    ])

    res = client.get(f'/v1/execution/{EXECUTION_ID}/summary')

    expected = '''Today is my birthday!'''

    assert expected == res.data.decode("utf-8")
