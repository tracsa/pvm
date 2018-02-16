import pika

from .logger import log


class Loop:

    def __init__(self, config:dict):
        self.config = config

    def callback(self, channel, method, properties, body):
        log.info(body)

    def start(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host = self.config['RABBIT_HOST'],
        ))
        channel = connection.channel()

        channel.queue_declare(
            queue = self.config['RABBIT_QUEUE'],
            durable = True,
        )

        channel.basic_consume(
            self.callback,
            queue = self.config['RABBIT_QUEUE'],
            consumer_tag = self.config['RABBIT_CONSUMER_TAG'],
            no_ack = True,
        )

        log.info('PVM started')

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            log.info('PVM stopped')
