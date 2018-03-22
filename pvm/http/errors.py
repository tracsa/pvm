class JsonReportedException(Exception):

    def __init__(self, errors):
        self.errors = errors

    def to_json(self):
        return { 'errors': self.errors, }

# 400
class BadRequest(JsonReportedException):
    status_code = 400

# 404
class NotFound(JsonReportedException):
    status_code = 404

# 422
class UnprocessableEntity(JsonReportedException):
    status_code = 422
