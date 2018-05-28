import logging


class CharpeHandler(logging.Handler):

    def emit(self, record):
        try:
            traceback = self.format(record)

            message = {
                'recipient': 'awonderfulcode@gmail.com',
                'subject': '[cacahuate] Server Error',
                'template': 'server-error',
                'data': {
                    'traceback': traceback,
                },
            }

            from pprint import pprint; pprint(message)
        except Exception:
            self.handleError(record)
