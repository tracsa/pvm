from functools import wraps


def comment(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        raise NotImplementedError('This function is commented')
    return wrapper
