from pvm.models import User, Token
import case_conversion
from random import choice
from string import ascii_letters


class BaseAuthProvider:

    def __init__(self, config):
        self.config = config

    def check_credentials(self):
        raise NotImplementedError('Must be implemented in subclasses')

    @property
    def username(self):
        return self.credentials['username']

    def get_user(self):
        # get namespace
        class_name = type(self).__name__
        class_name = case_conversion.snakecase(class_name)
        provider = class_name.split('_')[0]

        # get user identifier
        user_id = '{namespace}/{username}'.format(
            namespace=provider,
            username=self.username,
        )

        user = User.get_by('identifier', user_id)
        if user is None:
            user = User(identifier=user_id).save()

        return user

    def authenticate(self, credentials={}):
        self.credentials = credentials

        self.check_credentials()
        user = self.get_user()

        user.proxy.tokens.fill()

        if len(user.tokens) > 0:
            token = user.tokens[0]
        else:
            token = ''.join(choice(ascii_letters) for _ in range(32))
            token = Token(token=token).save()
            token.proxy.user.set(user)

        return {
            'data': {
                'username': user.identifier,
                'token': token.token,
            }
        }
