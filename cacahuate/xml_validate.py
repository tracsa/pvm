#!/usr/bin/env python3
import sys
from cacahuate.grammar import Condition
from cacahuate.xml import Xml
from cacahuate.http.wsgi import app, mongo
from xml.dom import pulldom
from cacahuate.grammar import Condition
from cacahuate.xml import get_text
from cacahuate.xml import NODES


def main(file=''):
    ids = []
    data_form = {}
    if file == '':
        if not len(sys.argv) == 2:
            sys.exit("Error no received file")
        file = sys.argv[1]
    param_auth_filter = {}
    conditions = []

    nodos = list(NODES)

    def check_id(node):
        if node.getAttribute('id'):
            id_element = node.getAttribute('id')

            if id_element not in ids:
                ids.append(id_element)
            else:
                sys.exit("Error id: '{}' repeat in {}".format(
                    id_element, file)
                )

    doc = pulldom.parse('xml/{}'.format(file))
    for event, node in doc:

        if event == pulldom.START_ELEMENT and \
         node.tagName in nodos and not node.tagName == 'if':
            check_id(node)
            doc.expandNode(node)
            if node.tagName == 'action':
                if node.getElementsByTagName("form"):
                    form_id = node.getElementsByTagName("form")[0]\
                     .getAttribute('id')
                    inputs = node.getElementsByTagName("input")
                    array_input = {}
                    for inpt in inputs:
                        array_input[inpt.getAttribute('name')] = \
                         inpt.getAttribute('default')
                    data_form[form_id] = array_input

                params = node.getElementsByTagName("param")
                for param in params:
                    if param.getAttribute('type'):
                        if param.getAttribute('type') == 'ref':
                            reference_form = \
                             (get_text(param).split('#')[1]).split('.')[0]
                            field_form = \
                                get_text(param).split('#')[1].split('.')[1]
                            try:
                                data_form[reference_form][field_form]
                            except Exception:
                                sys.exit(
                                    "Not param '{}' in form#{} in {}".format(
                                        field_form, reference_form, file
                                    )
                                )

            if node.tagName == 'validation':
                deps = node.getElementsByTagName("dep")
                for dep in deps:
                    form, field = get_text(dep).split('.')
                    try:
                        data_form[form][field]
                    except Exception:
                        sys.exit(
                            "Not dependence 'form#{}.{}' in {}".format(
                                form, field, file
                            )
                        )

        if event == pulldom.START_ELEMENT and node.tagName == 'if':
            check_id(node)

        if event == pulldom.START_ELEMENT and node.tagName == 'condition':
            doc.expandNode(node)
            conditions.append(get_text(node))

    con = Condition(data_form)
    for condition in conditions:
        if not con.parse(condition):
            sys.exit('Error {} in  {}'.format(condition, file))
    return True


if __name__ == '__main__':
    main()
