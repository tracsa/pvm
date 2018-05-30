#!/usr/bin/env python3
from coralillo import Engine
from itacate import Config
from xml.dom import pulldom
import logging
import logging.config
import os
import sys
import time
from lark.common import GrammarError, ParseError
from lark.lexer import LexError

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


def xml_validate(filename=None):
    ids = []
    data_form = {}

    if not filename:
        if not len(sys.argv) == 2:
            sys.exit("Must specify a file to analyze")
        filename = sys.argv[1]

    param_auth_filter = {}
    conditions = []

    def check_id(node):
        if node.getAttribute('id'):
            id_element = node.getAttribute('id')

            if id_element not in ids:
                ids.append(id_element)
            else:
                sys.exit("Duplicated id: '{}'".format(
                    id_element, filename
                ))

    doc = pulldom.parse(filename)
    for event, node in doc:
        if event != pulldom.START_ELEMENT:
            continue

        if node.tagName == 'condition':
            doc.expandNode(node)
            conditions.append(get_text(node))
            continue

        if not node.tagName in NODES:
            continue

        check_id(node)

        if node.tagName == 'if':
            continue

        # Expand and check this node. <if> nodes are not expanded
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
                        except KeyError:
                            sys.exit(
                                "Referenced param does not exist '{}'".format(
                                    reference_form+'.'+field_form,
                                )
                            )

        if node.tagName == 'validation':
            deps = node.getElementsByTagName("dep")

            for dep in deps:
                form, field = get_text(dep).split('.')

                try:
                    data_form[form][field]
                except KeyError:
                    sys.exit(
                        "Referenced dependency does not exist '{}'".format(
                            form + '.' + field,
                        )
                    )

    con = Condition(data_form)

    for condition in conditions:
        try:
            con.parse(condition)
        except GrammarError as e:
            sys.exit(str(e))
        except ParseError as e:
            sys.exit(str(e))
        except LexError as e:
            sys.exit(str(e))

    return True


if __name__ == '__main__':
    main()
