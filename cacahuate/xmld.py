#!/usr/bin/env python3
import os, sys
from cacahuate.grammar import Condition
from cacahuate.xml import Xml
from cacahuate.http.wsgi import app, mongo
from xml.dom import pulldom
from cacahuate.grammar import Condition

ids = []
errores = {'1':'id repetido'}

def main():

    file = sys.argv[1]
    nodos = ['action', 'call','validation', 'exit', 'request']

    doc = pulldom.parse('xml/{}'.format(file))
    for event, node in doc:

        if event == pulldom.START_ELEMENT and node.tagName in nodos:
            doc.expandNode(node)
            check_id(node)

        elif  event == pulldom.START_ELEMENT and node.tagName == 'if':
            check_id(node)

        elif  event == pulldom.START_ELEMENT and node.tagName == 'condition':
            check_id(node)
            doc.expandNode(node)
            condition = get_text(node)
            grammar = Condition(state['state'])

            value = grammar.parse(condition)





def check_id(node):
    if node.getAttribute('id'):
        id_element = node.getAttribute('id')
        if not id_element in ids:
            ids.append(id_element)
        else:
            print (id_element, ' repetido')
            sys.exit(1)


if __name__ == '__main__':
    main()

def get_text(node):
    node.normalize()
    if node.firstChild is not None:
        return node.firstChild.nodeValue or ''
    return ''