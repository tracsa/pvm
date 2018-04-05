import pika
from flask import g

from cacahuate.http.wsgi import app


def get_channel():
    channel = getattr(g, '_channel', None)

    if channel is None:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=app.config['RABBIT_HOST'],
        ))
        channel = connection.channel()

        channel.queue_declare(
            queue=app.config['RABBIT_QUEUE'],
            durable=True,
        )

        g._channel = channel

    return channel
