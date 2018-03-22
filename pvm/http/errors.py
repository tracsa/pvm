from werkzeug.exceptions import BadRequest

# 400
class NeedsJson(BadRequest): pass
