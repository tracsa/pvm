import json
import logging
import pika


class CharpeHandler(logging.Handler):

    def __init__(self, host, medium, exchange, params):
        super().__init__()

        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=host,
        ))

        self.medium = medium
        self.exchange = exchange
        self.params = params
        self.channel = connection.channel()

    def emit(self, record):
        try:
            traceback = self.format(record)

            params = self.params.copy()
            params['data'] = {
                'traceback': traceback,
            }

            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=self.medium,
                body=json.dumps(params),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
            )

        except Exception:
            self.handleError(record)
