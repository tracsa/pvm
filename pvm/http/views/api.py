from flask import request, jsonify, json
import pika

from pvm.http.wsgi import app
from pvm.http.forms import ContinueProcess
from pvm.http.middleware import requires_json
from pvm.http.errors import BadRequest, NotFound, UnprocessableEntity, Unauthorized
from pvm.errors import ProcessNotFound, ElementNotFound, ValidationErrors
from pvm.models import Execution, Pointer, User, Token, Activity, Questionaire
from pvm.rabbit import get_channel
from pvm.xml import Xml, get_ref
from pvm.validation import validate_form

@app.route('/', methods=['GET', 'POST'])
@requires_json
def index():
    if request.method == 'GET':
        return {
            'hello': 'world',
        }
    elif request.method == 'POST':
        return request.json

@app.route('/v1/execution', methods=['POST'])
@requires_json
def start_process():
    if 'process_name' not in request.json:
        raise BadRequest([{
            'detail': 'process_name is required',
            'where': 'request.body.process_name',
        }])

    try:
        xml = Xml.load(app.config, request.json['process_name'])
    except ProcessNotFound as e:
        raise NotFound([{
            'detail': '{} process does not exist'.format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    try:
        start_point = xml.find(lambda e:e.getAttribute('class') == 'start')
    except ElementNotFound as e:
        raise UnprocessableEntity([{
            'detail': '{} process does not have a start node, thus cannot be started'.format(request.json['process_name']),
            'where': 'request.body.process_name',
        }])

    # Check if auth node is present
    auth = start_point.getElementsByTagName('auth')
    auth_ref = None

    if len(auth) == 1:
        auth_node = auth[0]

        # Authorization required but not provided, notify
        if request.authorization is None:
            raise Unauthorized([{
                'detail': 'You must provide basic authorization headers',
                'where': 'request.authorization',
            }])

        identifier = request.authorization['username']
        token = request.authorization['password']

        user = User.get_by('identifier', identifier)
        token = Token.get_by('token', token)

        if user is None or token is None or token.proxy.user.get().id != user.id:
            raise Unauthorized([{
                'detail': 'Your credentials are invalid, sorry',
                'where': 'request.authorization',
            }])

        auth_ref = get_ref(auth_node)

    # check if there are any forms present
    form_array = start_point.getElementsByTagName('form-array')
    collected_forms = []

    if len(form_array) == 1:
        form_array_node = form_array[0]

        errors = []

        for index, form in enumerate(form_array_node.getElementsByTagName('form')):
            try:
                data = validate_form(index, form, request.json)
                collected_forms.append((get_ref(form), data))
            except ValidationErrors as e:
                errors += e.errors

        if len(errors) > 0:
            raise BadRequest(ValidationErrors(errors).to_json())

    # Now we can save the data
    execution = Execution(
        process_name = xml.name,
    ).save()

    pointer = Pointer(
        node_id = start_point.getAttribute('id'),
    ).save()

    pointer.proxy.execution.set(execution)

    if auth_ref is not None:
        activity = Activity(ref=auth_ref).save()
        activity.proxy.user.set(user)
        activity.proxy.execution.set(execution)

    if len(collected_forms) > 0:
        for ref, form_data in collected_forms:
            ques = Questionaire(ref=ref, data=form_data).save()
            ques.proxy.execution.set(execution)

    channel = get_channel()
    channel.basic_publish(
        exchange = '',
        routing_key = app.config['RABBIT_QUEUE'],
        body = json.dumps({
            'command': 'step',
            'process': execution.process_name,
            'pointer_id': pointer.id,
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
        ),
    )

    return {
        'data': execution.to_json(),
    }, 201

@app.route('/v1/pointer', methods=['POST'])
@requires_json
def continue_process():
    data = ContinueProcess.validate(**request.form.to_dict())

# TODO validate specific data required for the node to continue
    channel = get_channel()
    channel.basic_publish(
        exchange = '',
        routing_key = app.config['RABBIT_QUEUE'],
        body = json.dumps({
            'command': 'step',
            'process': data.execution.process_name,
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
        ),
    )

    return {
        'data': {
            'detail': 'accepted',
        },
    }, 202
