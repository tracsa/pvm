class JsonReportedException(Exception):

    def __init__(self, errors, headers=None):
        self.errors = errors
        self.headers = headers if headers else {}

    def to_json(self):
        return {'errors': self.errors}

# 400


class BadRequest(JsonReportedException):
    status_code = 400

# 401


class Unauthorized(JsonReportedException):
    status_code = 401

    def __init__(self, errors):
        super().__init__(errors, {
            'WWW-Authenticate': 'Basic realm="User Visible Realm"',
        })

# 403


class Forbidden(JsonReportedException):
    status_code = 403

# 404


class NotFound(JsonReportedException):
    status_code = 404

# 422


class UnprocessableEntity(JsonReportedException):
    status_code = 422
