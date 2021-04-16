from collections import deque
from datetime import datetime, timezone
from typing import TextIO, Callable
from jsonpath_rw import parse as jsonpathparse
from xml.dom import pulldom
from xml.dom.minidom import Element
import xml.dom.minidom as minidom
from xml.sax._exceptions import SAXParseException
import json
import os
import pika

from cacahuate.errors import ProcessNotFound, ElementNotFound, MalformedProcess
from cacahuate.jsontypes import SortedMap
from cacahuate.models import Execution, Pointer
from cacahuate.forms import compact_values
from cacahuate.templates import render_or
from cacahuate.mongo import pointer_entry


XML_ATTRIBUTES = {
    'public': lambda a: a == 'true',
    'author': str,
    'date': str,
    'name': str,
    'description': lambda x: x,
}

NODES = (
    'action',
    'validation',
    'exit',
    'if',
    'elif',
    'else',
    'request',
    'call',
)


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

    def get_file_path(self):
        return os.path.join(self.config['XML_PATH'], self.filename)

    def get_dom(self):
        return minidom.parse(self.get_file_path())

    # Interpolate name
    def get_name(self, context={}):
        return render_or(self._name, self.filename, context)

    def set_name(self, name):
        self._name = name

    name = property(get_name, set_name)

    def name_template(self):
        return self._name

    # Interpolate description
    def get_description(self, context={}):
        return render_or(self._description, self._description, context)

    def set_description(self, description):
        self._description = description

    description = property(get_description, set_description)

    def description_template(self):
        return self._description

    @classmethod
    def load(cls, config: dict, common_name: str, direct=False) -> TextIO:
        ''' Loads an xml file and returns the corresponding TextIOWrapper for
        further usage. The file might contain multiple versions so the latest
        one is chosen.

        common_name is the prefix of the file to find. If multiple files with
        the same prefix are found the last in lexicographical order is
        returned.'''
        if direct:
            # skip looking for the most recent version
            return Xml(config, common_name)

        pieces = common_name.split('.')

        try:
            name = pieces[0]
            version = pieces[1]
        except IndexError:
            name, version = common_name, None

        files = reversed(sorted(os.listdir(config['XML_PATH'])))

        for filename in files:
            fpieces = filename.split('.')

            try:
                fname = fpieces[0]
                fversion = fpieces[1]
            except IndexError:
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
        # the first set of values
        context = compact_values(input)

        # save the data
        execution = Execution(
            process_name=self.filename,
            name=self.get_name(context),
            name_template=self.name_template(),
            description=self.get_description(context),
            description_template=self.description_template(),
            started_at=datetime.now(),
            status='ongoing',
        ).save()

        pointer = Pointer(
            node_id=node.id,
            name=node.get_name(context),
            description=node.get_description(context),
        ).save()
        pointer.proxy.execution.set(execution)

        # log to mongo
        collection = mongo[self.config['POINTER_COLLECTION']]
        collection.insert_one(pointer_entry(
            node,
            pointer.name,
            pointer.description,
            execution,
            pointer
        ))

        collection = mongo[self.config['EXECUTION_COLLECTION']]
        collection.insert_one({
            '_type': 'execution',
            'id': execution.id,
            'name': execution.name,
            'process_name': execution.process_name,
            'description': execution.description,
            'status': execution.status,
            'started_at': execution.started_at,
            'finished_at': None,
            'state': self.get_state(),
            'values': {
                '_execution': [{
                    'id': execution.id,
                    'name': execution.name,
                    'process_name': execution.process_name,
                    'description': execution.description,
                    'started_at': datetime.now(timezone.utc).isoformat(),
                }],
            },
            'actors': {},
            'actor_list': [],
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

    def make_iterator(xmlself, iterables):
        class Iter():

            def __init__(self, file_path):
                self.parser = pulldom.parse(open(file_path))
                self.block_stack = deque()

            def find(self, testfunc: Callable[[Element], bool]) -> Element:
                ''' Given an interator returned by the previous function, tries
                to find the first node matching the given condition '''
                for element in self:
                    if testfunc(element):
                        return element

                raise ElementNotFound(
                    'node matching the given condition was not found'
                )

            def get_next_condition(self):
                for event, node in self.parser:
                    if event != pulldom.START_ELEMENT:
                        continue

                    if node.tagName != 'condition':
                        raise ElementNotFound(
                            'Requested a condition but found {}'.format(
                                node.tagName
                            )
                        )

                    self.parser.expandNode(node)

                    return get_text(node)

                raise ElementNotFound('Condition not found')

            def next_skipping_elifelse(self):
                old_stack = len(self.block_stack)
                proposed_next = next(self)
                new_stack = len(self.block_stack)

                if new_stack < old_stack:
                    while proposed_next.tagName in ('elif', 'else'):
                        self.parser.expandNode(proposed_next)
                        proposed_next = next(self)

                return proposed_next

            def expand(self, node):
                self.parser.expandNode(node)

            def __next__(self):
                try:
                    for event, node in self.parser:
                        if event == pulldom.END_ELEMENT and \
                                node.tagName == 'block':
                            self.block_stack.pop()
                        if event == pulldom.START_ELEMENT:
                            if node.tagName == 'block':
                                self.block_stack.append(1)
                            elif node.tagName in iterables:
                                return node
                except SAXParseException:
                    raise MalformedProcess

                raise StopIteration

            def __iter__(self):
                return self

        return Iter(xmlself.get_file_path())

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
        items = []

        for node in xmliter:
            built_node = make_node(node, xmliter)

            items.append(built_node.get_state())

        return SortedMap(items, key='id').to_json()

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


def input_to_dict(input, context=None):
    if not context:
        context = {}

    input_attrs = [
        (attr, func(input.getAttribute(attr)))
        for attr, func in SUPPORTED_ATTRS.items()
    ]

    options = []
    for opt in input.getElementsByTagName('option'):
        ref_attr = opt.getAttribute('ref')
        if ref_attr:
            ref_type, ref_path = ref_attr.split('#')
            if ref_type == 'form':
                if not len(jsonpathparse(ref_path).find(context)):
                    continue

                label_path = opt.getAttribute('label')
                value_path = opt.getAttribute('value')

                match = jsonpathparse(ref_path).find(context)[0].value.all()
                for localdata in match:
                    options.append({
                        'value': jsonpathparse(value_path).find(localdata)[0].value,
                        'label': jsonpathparse(label_path).find(localdata)[0].value,
                    })

        else:
            options.append({
                'value': opt.getAttribute('value'),
                'label': opt.getAttribute('label') or get_text(opt),
            })

    input_attrs.append(('options', options))

    return dict(filter(
        lambda a: a[1],
        input_attrs
    ))


def form_to_dict(form, context=None):
    if not context:
        context = {}

    inputs = form.getElementsByTagName('input')

    form_dict = {
        'ref': form.getAttribute('id'),
        'inputs': [],
    }

    if form.getAttribute('multiple'):
        form_dict['multiple'] = form.getAttribute('multiple')

    for input in inputs:
        form_dict['inputs'].append(input_to_dict(input, context=context))

    return form_dict


def get_element_by(dom, tag_name, attr, value):
    for el in dom.getElementsByTagName(tag_name):
        if el.getAttribute(attr) == value:
            return el
