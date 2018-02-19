""" Here is defined the node class and its subclasses, which define the kinds
of directions that this virtual machine can follow """

class Node:

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
