from werkzeug.exceptions import BadRequest

# 400
class NeedsJson(BadRequest): pass

class MissingField(BadRequest):

    def __init__(self, field):
        super().__init__('{} is missing'.format(field))
        self.field = field
