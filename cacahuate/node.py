""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
from case_conversion import pascalcase
from typing import Iterator
from xml.dom.minidom import Element

from cacahuate.utils import user_import
from cacahuate.xml import get_text, NODES
from cacahuate.logger import log
from cacahuate.grammar import Condition
from cacahuate.errors import ElementNotFound, IncompleteBranch


class AuthParam:

    def __init__(self, param):
        self.name = param.getAttribute('name')
        self.value = get_text(param)
        self.type = param.getAttribute('type')


class Node:
    ''' An XML tag that represents an action or instruction for the virtual
    machine '''

    def __init__(self, element):
        for attrname, value in element.attributes.items():
            setattr(self, attrname, value)

    def is_async(self):
        raise NotImplementedError('Must be implemented in subclass')


class Action(Node):
    ''' A node from the process's graph. It is initialized from an Element
    '''

    def __init__(self, element):
        super().__init__(element)

        # node info
        node_info = element.getElementsByTagName('node-info')

        name = ''
        description = ''

        if len(node_info) == 1:
            node_info = node_info[0]

            node_name = node_info.getElementsByTagName('name')
            name = get_text(node_name[0])

            node_description = node_info.getElementsByTagName('description')
            description = get_text(node_description[0])

        self.name = name
        self.description = description

        # Actor resolving
        self.auth_params = []
        self.auth_backend = None

        filter_q = element.getElementsByTagName('auth-filter')

        if len(filter_q) > 0:
            filter_node = filter_q[0]

            self.auth_backend = filter_node.getAttribute('backend')
            self.auth_params = list(map(
                lambda x: AuthParam(x),
                filter_node.getElementsByTagName('param')
            ))

    def is_async(self):
        return True

    def resolve_params(self, execution=None):
        computed_params = {}

        for param in self.auth_params:
            if execution is not None and param.type == 'ref':
                user_ref = param.value.split('#')[1].strip()

                try:
                    actor = next(
                        execution.proxy.actors.q().filter(ref=user_ref)
                    )

                    value = actor.proxy.user.get().identifier
                except StopIteration:
                    value = None
            else:
                value = param.value

            computed_params[param.name] = value

        return computed_params

    def get_actors(self, config, execution):
        if not self.auth_params:
            return []

        HiPro = user_import(
            self.auth_backend,
            'HierarchyProvider',
            config['HIERARCHY_PROVIDERS'],
            'cacahuate.auth.hierarchy',
        )

        hierarchy_provider = HiPro(config)

        return hierarchy_provider.find_users(
            **self.resolve_params(execution)
        )

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
        }


class Exit(Node):
    ''' A node that kills an execution with some status '''

    def is_async(self):
        return False


def make_node(element):
    ''' returns a build Node object given an Element object '''
    if element.tagName not in NODES:
        raise ValueError('Class definition not found for node: {}'.format(class_name))

    class_name = pascalcase(element.tagName)
    available_classes = __import__(__name__).node

    return getattr(available_classes, class_name)(element)
