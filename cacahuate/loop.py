import logging
import pika
import traceback

from .handler import Handler

LOGGER = logging.getLogger(__name__)


class Loop:

    def __init__(self, config: dict):
        self.config = config
        self.handler = Handler(config)

    def start(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.config['RABBIT_HOST'],
        ))
        channel = connection.channel()

        channel.queue_declare(
            queue=self.config['RABBIT_QUEUE'],
            durable=True,
        )
        LOGGER.info('Declared queue {}'.format(self.config['RABBIT_QUEUE']))

        channel.basic_consume(
            self.config['RABBIT_QUEUE'],
            self.handler,
            auto_ack=self.config['RABBIT_NO_ACK'],
            consumer_tag=self.config['RABBIT_CONSUMER_TAG'],
        )

        LOGGER.info('cacahuate started')

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            LOGGER.info('cacahuate stopped')
        except Exception:
            LOGGER.error(traceback.format_exc())
