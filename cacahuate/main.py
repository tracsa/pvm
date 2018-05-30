#!/usr/bin/env python3
from coralillo import Engine
from itacate import Config
from xml.dom import pulldom
import logging
import logging.config
import os
import sys
import time

from cacahuate.indexes import create_indexes
from cacahuate.loop import Loop
from cacahuate.models import bind_models
from cacahuate.xml import NODES, get_text
from cacahuate.grammar import Condition


def main():
    # Load the config
    config = Config(os.path.dirname(os.path.realpath(__file__)))
    config.from_object('cacahuate.settings')
    config.from_envvar('CACAHUATE_SETTINGS', silent=True)

    # Set the timezone
    os.environ['TZ'] = config['TIMEZONE']
    time.tzset()

    # Setup logging
    logging.config.dictConfig(config['LOGGING'])

    # Load the models
    eng = Engine(
        host=config['REDIS_HOST'],
        port=config['REDIS_PORT'],
        db=config['REDIS_DB'],
    )
    bind_models(eng)

    # Create mongo indexes
    create_indexes(config)

    # start the loop
    loop = Loop(config)
    loop.start()


def xml_validate(file=''):
    ids = []
    data_form = {}
    if file == '':
        if not len(sys.argv) == 2:
            sys.exit("Error no received file")
        file = sys.argv[1]
    param_auth_filter = {}
    conditions = []

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
         node.tagName in NODES and not node.tagName == 'if':
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
