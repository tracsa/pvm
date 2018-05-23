from datetime import datetime
from jinja2 import Template, TemplateError
from typing import Iterator, TextIO, Callable, Optional, Any, Union
from xml.dom import pulldom
from xml.dom.minidom import Element
from xml.sax._exceptions import SAXParseException
import json
import os
import pika

from cacahuate.errors import ProcessNotFound, ElementNotFound, MalformedProcess
from cacahuate.jsontypes import SortedMap
from cacahuate.models import Execution, Pointer

XML_ATTRIBUTES = {
    'public': lambda a: a == 'true',
    'author': str,
    'date': str,
    'name': str,
    'description': lambda x: x,
}

NODES = ('action', 'validation', 'exit', 'if', 'request', 'call')


class Xml:

    def __init__(self, config, filename):
        try:
            self.id, self.version, _ = filename.split('.')
        except ValueError:
            raise MalformedProcess(
                'Name of process is invalid, must be name.version.xml'
            )

        self.versions = [self.version]
        self.filename = filename
        self.config = config

        try:
            info_node = self.get_info_node()
        except StopIteration:
            raise MalformedProcess('This process lacks the process-info node')

        if info_node.tagName != 'process-info':
            raise MalformedProcess('process-info node must be the first node')

        for attr, func in XML_ATTRIBUTES.items():
            try:
                node = info_node.getElementsByTagName(attr)[0]
            except IndexError:
                raise MalformedProcess(
                    'Process\' metadata lacks node {}'.format(attr)
                )

            setattr(self, attr, func(get_text(node)))

    def get_name(self, collected_forms=[]):
        context = dict()
        for form in collected_forms:
            form_dict = dict()

            for name, input in form['inputs']['items'].items():
                form_dict[name] = input['value_caption']

            context[form['ref']] = form_dict

        try:
            return Template(self._name).render(**context)
        except TemplateError:
            return self.filename

    def set_name(self, name):
        self._name = name

    name = property(get_name, set_name)

    @classmethod
    def load(cls, config: dict, common_name: str, direct=False) -> Union[TextIO, Xml]:
        ''' Loads an xml file and returns the corresponding TextIOWrapper for
        further usage. The file might contain multiple versions so the latest
        one is chosen.

        common_name is the prefix of the file to find. If multiple files with
        the same prefix are found the last in lexicographical order is
        returned.'''
        if direct:
            # skip looking for the most recent version
            return Xml(config, common_name)

        try:
            name, version = common_name.split('.')
        except ValueError:
            name = common_name
            version = None # type: ignore
            # name, version = common_name, None

        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        for filename in files:
            try:
                fname, fversion, _ = filename.split('.')
            except ValueError:
                # Process with malformed name, sorry
                continue

            if fname == name:
                if version:
                    if fversion == version:
                        return Xml(config, filename)
                else:
                    return Xml(config, filename)

        else:
            raise ProcessNotFound(common_name)

    def start(self, node, input, mongo, channel, user_identifier):
        # save the data
        execution = Execution(
            process_name=self.filename,
            name=self.get_name(input),
            description=self.description,
        ).save()
        pointer = Pointer(
            node_id=node.id,
            name=node.name,
            description=node.description,
        ).save()
        pointer.proxy.execution.set(execution)

        # log to mongo
        collection = mongo[self.config['POINTER_COLLECTION']]
        res = collection.insert_one(node.pointer_entry(execution, pointer))

        collection = mongo[self.config['EXECUTION_COLLECTION']]
        res = collection.insert_one({
            '_type': 'execution',
            'id': execution.id,
            'name': execution.name,
            'description': execution.description,
            'status': 'ongoing',
            'started_at': datetime.now(),
            'finished_at': None,
            'state': self.get_state(),
            'values': {},
            'actors': {},
        })

        # trigger rabbit
        channel.basic_publish(
            exchange='',
            routing_key=self.config['RABBIT_QUEUE'],
            body=json.dumps({
                'command': 'step',
                'pointer_id': pointer.id,
                'user_identifier': user_identifier,
                'input': input,
            }),
            properties=pika.BasicProperties(
                delivery_mode=2,
            ),
        )

        return execution

    def make_iterator(self, iterables):

        class Iter():

            def __init__(self, config, filename):
                self.parser = pulldom.parse(
                    open(os.path.join(config['XML_PATH'], filename))
                )

            def find(self, testfunc: Callable[[Element], bool]) -> Element:
                ''' Given an interator returned by the previous function, tries
                to find the first node matching the given condition '''
                # Since we already consumed the start node on initialization,
                # this fix is needed for find() to be stable
                for element in self:
                    if testfunc(element):
                        return element

                raise ElementNotFound(
                    'node matching the given condition was not found'
                )

            def get_next_condition(self):
                for event, node in self.parser:
                    if event == pulldom.START_ELEMENT and \
                            node.tagName == 'condition':
                        self.parser.expandNode(node)
                        condition = get_text(node)

                        return condition

            def expand(self, node):
                self.parser.expandNode(node)

            def __next__(self):
                try:
                    for event, node in self.parser:
                        if event == pulldom.START_ELEMENT and \
                                node.tagName in iterables:

                            return node
                except SAXParseException:
                    raise MalformedProcess

                raise StopIteration

            def __iter__(self):
                return self

        return Iter(self.config, self.filename)

    def get_info_node(self):
        xmliter = self.make_iterator('process-info')
        info_node = next(xmliter)
        xmliter.parser.expandNode(info_node)

        return info_node

    def __iter__(self):
        ''' Returns an inerator over the nodes and edges of a process defined
        by the xmlfile descriptor. Uses XMLPullParser so no memory is consumed
        for this task. '''
        return self.make_iterator(NODES)

    def get_state(self):
        from cacahuate.node import make_node  # noqa

        xmliter = iter(self)

        return SortedMap(map(
            lambda node: node.get_state(),
            filter(
                lambda node: node,
                map(
                    lambda node: make_node(node, xmliter),
                    xmliter
                )
            )
        ), key='id').to_json()

    @classmethod
    def list(cls, config):
        # Get all processes
        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        # Load only the oldest processes
        processes = []

        for filename in files:
            try:
                id, version, _ = filename.split('.')
            except ValueError:
                continue

            try:
                xml = cls.load(config, filename, direct=True)
            except ProcessNotFound:
                continue
            except MalformedProcess:
                continue

            if not xml.public:
                continue

            if len(processes) == 0 or processes[-1].id != id:
                processes.append(xml)
            else:
                processes[-1].versions.append(version)

        return processes

    def to_json(self):
        return {
            'id': self.id,
            'version': self.version,
            'author': self.author,
            'date': self.date,
            'name': self.name,
            'description': self.description,
            'versions': self.versions,
        }


def get_node_info(node):
    # Get node-info
    node_info = node.getElementsByTagName('node-info')
    name = None
    description = None

    if len(node_info) == 1:
        node_info = node_info[0]

        node_name = node_info.getElementsByTagName('name')
        name = get_text(node_name[0])

        node_description = node_info.getElementsByTagName('description')
        description = get_text(node_description[0])

    return {
        'name': name,
        'description': description,
    }


def get_text(node):
    node.normalize()

    if node.firstChild is not None:
        return node.firstChild.nodeValue or ''

    return ''


def get_options(node):
    options = []

    for option in node.getElementsByTagName('option'):
        option.normalize()

        options.append({
            'value': option.getAttribute('value'),
            'label': option.firstChild.nodeValue,
        })

    return options


def get_input_specs(node):
    specs = []

    for field in node.getElementsByTagName('input'):
        spec = {
            attr: SUPPORTED_ATTRS[attr](field.getAttribute(attr))
            for attr in SUPPORTED_ATTRS
            if field.getAttribute(attr)
        }

        spec['options'] = get_options(field)

        specs.append(spec)

    return specs


def get_form_specs(node):
    form_array = node.getElementsByTagName('form-array')

    if len(form_array) == 0:
        return []

    form_array = form_array[0]

    specs = []

    for form in form_array.getElementsByTagName('form'):
        specs.append({
            'ref': form.getAttribute('id'),
            'multiple': form.getAttribute('multiple'),
            'inputs': get_input_specs(form)
        })

    return specs


SUPPORTED_ATTRS = {
    'default': str,
    'helper': str,
    'label': str,
    'name': str,
    'placeholder': str,
    'provider': str,
    'regex': str,
    'required': lambda x: bool(x),
    'type': str,
}


def input_to_dict(input):
    input_attrs = [
        (attr, func(input.getAttribute(attr)))
        for attr, func in SUPPORTED_ATTRS.items()
    ] + [('options', list(map(
        lambda e: {
            'value': e.getAttribute('value'),
            'label': get_text(e),
        },
        input.getElementsByTagName('option'),
    )))]

    return dict(filter(
        lambda a: a[1],
        input_attrs
    ))


def form_to_dict(form):
    inputs = form.getElementsByTagName('input')

    form_dict = {
        'ref': form.getAttribute('id'),
        'inputs': [],
    }

    if form.getAttribute('multiple'):
        form_dict['multiple'] = form.getAttribute('multiple')

    for input in inputs:
        form_dict['inputs'].append(input_to_dict(input))

    return form_dict
