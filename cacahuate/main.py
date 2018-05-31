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
    if not filename:
        if not len(sys.argv) == 2:
            sys.exit("Must specify a file to analyze")
        filename = sys.argv[1]

    ids = []
    data_form = {}
    passed_nodes = []

    def check_id(node):
        if node.getAttribute('id'):
            id_element = node.getAttribute('id')

            if id_element not in ids:
                ids.append(id_element)
            else:
                sys.exit("{}: Duplicated id: '{}'".format(
                    filename,
                    id_element,
                ))

    doc = pulldom.parse(filename)

    for event, node in doc:
        if event != pulldom.START_ELEMENT:
            continue

        if node.tagName == 'condition':
            doc.expandNode(node)

            try:
                Condition().parse(get_text(node))
            except GrammarError:
                sys.exit('{}: Grammar error in condition'.format(filename))
            except ParseError:
                sys.exit('{}: Parse error in condition'.format(filename))
            except LexError:
                sys.exit('{}: Lex error in condition'.format(filename))
            except KeyError as e:
                sys.exit(
                    '{}: variable used in condition does not exist: {}'.format(
                        filename,
                        str(e),
                    )
                )

            continue

        if node.tagName not in NODES:
            continue

        # Duplicate ids
        check_id(node)

        if node.tagName == 'if':
            continue

        # Expand and check this node. <if> nodes are not expanded
        doc.expandNode(node)

        # Check auth-filter params
        params = node.getElementsByTagName("param")

        for param in params:
            if param.getAttribute('type') != 'ref':
                continue

            ref_type, ref = get_text(param).split('#')

            if ref_type == 'form':
                reference_form, field_form = ref.split('.')

                try:
                    data_form[reference_form][field_form]
                except KeyError:
                    sys.exit(
                        "{}: Referenced param does not exist '{}'".format(
                            filename,
                            reference_form+'.'+field_form,
                        )
                    )
            elif ref_type == 'user':
                if ref not in passed_nodes:
                    sys.exit(
                        '{}: Referenced user is never created: {}'.format(
                            filename,
                            ref,
                        )
                    )

        # Check dependencies
        deps = node.getElementsByTagName("dep")

        for dep in deps:
            form, field = get_text(dep).split('.')

            try:
                data_form[form][field]
            except KeyError:
                sys.exit(
                    "{}: Referenced dependency does not exist '{}'".format(
                        filename,
                        form + '.' + field,
                    )
                )

        # fill forms for later usage
        forms = node.getElementsByTagName('form')

        for form in forms:
            form_id = form.getAttribute('id')
            inputs = form.getElementsByTagName("input")
            array_input = {}

            for inpt in inputs:
                array_input[inpt.getAttribute('name')] = \
                 inpt.getAttribute('default')

            data_form[form_id] = array_input

        # add this node to the list of revised nodes
        has_auth_filter = len(node.getElementsByTagName('auth-filter')) > 0

        if has_auth_filter:
            passed_nodes.append(node.getAttribute('id'))

    print('{} seems correct...'.format(filename), file=sys.stderr)


if __name__ == '__main__':
    main()
