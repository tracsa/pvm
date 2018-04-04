#!/usr/bin/env python
import pika
import simplejson as json
import os
import argparse
from itacate import Config

from pvm.logger import log


class Trigger:

    def __init__(self):
        config = Config(os.path.dirname(os.path.realpath(__file__)))
        config.from_pyfile('settings.py')
        config.from_envvar('PVM_SETTINGS', silent=True)

        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host = config['RABBIT_HOST'],
        ))
        channel = connection.channel()

        channel.queue_declare(
            queue = config['RABBIT_QUEUE'],
            durable = True,
        )

        self.config = config
        self.channel = channel

    def start(self, args):
        self.channel.basic_publish(
            exchange = '',
            routing_key = self.config['RABBIT_QUEUE'],
            body = json.dumps({
                'command': 'start',
                'process': args.process,
            }),
            properties = pika.BasicProperties(
                delivery_mode = 2, # make message persistent
            ),
        )

        log.info("Process queued for start")

    def step(self, args):
        self.channel.basic_publish(
            exchange = '',
            routing_key = self.config['RABBIT_QUEUE'],
            body = json.dumps({
                'command': 'step',
                'pointer_id': args.pointer_id,
                'data': dict(args.data) if args.data is not None else dict(),
            }),
            properties = pika.BasicProperties(
                delivery_mode = 2, # make message persistent
            ),
        )


def make_tuple(arg:str):
    value = tuple(arg.split('='))

    if len(value) != 2:
        raise argparse.ArgumentTypeError('must be of the form key=value')

    return value

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trigger a process')
    subparsers = parser.add_subparsers(help='Type of command to trigger')
    trigger = Trigger()

    start_parser = subparsers.add_parser('start', description='starts a new process')
    start_parser.add_argument('process', help='The process to start')
    start_parser.set_defaults(func=trigger.start)

    continue_parser = subparsers.add_parser('step', description='continues the execution of a process')
    continue_parser.add_argument('pointer_id', help='the id of the pointer to restore')
    continue_parser.add_argument('-d', '--data', action='append', type=make_tuple)
    continue_parser.set_defaults(func=trigger.step)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.parse_args('-h')

    args.func(args)
