import logging
import traceback
from threading import Thread
from queue import Queue
from functools import partial

import pika

from .handler import Handler

LOGGER = logging.getLogger(__name__)


def ack_message(channel, delivery_tag, ok):
    if channel.is_open:
        if ok:
            LOGGER.debug('Message acked {}'.format(delivery_tag))
            channel.basic_ack(delivery_tag)
        else:
            LOGGER.debug('Message rejected {}'.format(delivery_tag))
            channel.basic_reject(delivery_tag, requeue=False)
    else:
        LOGGER.warning("Found closed channel while trying to ACK")


def handler_loop(connection, config, queue):
    handler = Handler(config)

    LOGGER.info('Handler thread started')

    # A Rabbitmq connection specific to this thread
    thread_connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=config['RABBIT_HOST'],
        credentials=pika.PlainCredentials(
            config['RABBIT_USER'],
            config['RABBIT_PASS'],
        ),
    ))
    thread_channel = thread_connection.channel()

    while True:
        stop, (channel, method, properties, body) = queue.get()

        if stop:
            LOGGER.debug('Stop request received from queue')
            break

        LOGGER.debug('Message read from queue: {}'.format(method.delivery_tag))

        try:
            handler(thread_channel, body)

            cb = partial(ack_message, channel, method.delivery_tag, True)
        except Exception:
            cb = partial(ack_message, channel, method.delivery_tag, False)
            LOGGER.error(traceback.format_exc())
        finally:
            connection.add_callback_threadsafe(cb)

    LOGGER.info('Handler thread stopped')


def handle_message(channel, method, properties, body, connection, queue):
    queue.put((False, (channel, method, properties, body)))


def start(config):
    # Setup the amqp protocol
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=config['RABBIT_HOST'],
        credentials=pika.PlainCredentials(
            config['RABBIT_USER'],
            config['RABBIT_PASS'],
        ),
        heartbeat=config['RABBIT_HEARTBEAT'],
    ))
    channel = connection.channel()

    channel.queue_declare(
        queue=config['RABBIT_QUEUE'],
        durable=True,
    )
    LOGGER.info('Declared queue {}'.format(config['RABBIT_QUEUE']))

    # Setup a thread for processing messages
    queue = Queue()

    thread = Thread(target=partial(handler_loop, connection, config, queue))

    # Start the thread
    thread.start()

    # Attach a handler to the consumer loop
    channel.basic_consume(
        config['RABBIT_QUEUE'],
        partial(handle_message, connection=connection, queue=queue),
        consumer_tag=config['RABBIT_CONSUMER_TAG'],
    )

    # Start the consumer loop
    try:
        LOGGER.info('cacahuate started')
        channel.start_consuming()
    except KeyboardInterrupt:
        LOGGER.info('cacahuate stopped')
        queue.put((True, (None, None, None, None)))
        channel.stop_consuming()
        thread.join()

    connection.close()
