#!/usr/bin/env python
import pika
import json
import os
import argparse
from itacate import Config

from lib.logger import log

def main(args):
    config = Config(os.path.dirname(os.path.realpath(__file__)))
    config.from_pyfile('settings.py')
    config.from_envvar('PVM_SETTINGS', silent=False)

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host = config['RABBIT_HOST'],
    ))
    channel = connection.channel()

    channel.queue_declare(
        queue = config['RABBIT_QUEUE'],
        durable = True,
    )

    channel.basic_publish(
        exchange = '',
        routing_key = config['RABBIT_QUEUE'],
        body = json.dumps({
            'process': args.process,
            'command': 'start',
        }),
        properties = pika.BasicProperties(
            delivery_mode = 2, # make message persistent
        ),
    )

    log.info("Message sent")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trigger a process')

    parser.add_argument('process', help='The process to start')

    args = parser.parse_args()

    main(args)
