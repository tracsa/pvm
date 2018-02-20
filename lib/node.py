""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """
import case_conversion


class Node:
    ''' A node from the process's graph. It is initialized from an ET.Element
    '''

    def __init__(self, id, attrib):
        self.id = id
        self.attrib = attrib

    def __call__(self):
        ''' Executes this node's action. Can be triggering a message or
        something similar '''
        raise NotImplementedError('Should be implemented for subclasses')

    def can_continue(self):
        ''' Determines if this node has everything it needs to continue the
        execution of the script '''
        raise NotImplementedError('Should be implemented for subclasses')

    def next(self):
        ''' Gets the next node in the graph, if it fails raises an exception.
        Assumes that can_continue() has been called before '''
        raise NotImplementedError('Should be implemented for subclasses')


class StartNode(Node): pass


def make_node(element):
    ''' returns a build Node object given an ET.Element object '''
    if 'class' not in element.attrib:
        raise KeyError('Must have the class atrribute')

    class_name = case_conversion.pascalcase(element.attrib['class']) + 'Node'
    available_classes = __import__(__name__).node

    if class_name not in dir(available_classes):
        raise ValueError('Class definition not found: {}'.format(class_name))

    return getattr(available_classes, class_name)(
        element.attrib.get('id'),
        element.attrib,
    )
