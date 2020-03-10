from functools import wraps
from webob import Response

# Note: assumes application/json-compatible media type
def created(location):
    def wrapped(func):
        @wraps(func)
        def decorator(req, params, config):
            urlparams = func(req, params, config)
            return Response(
                status=201,
                location=req.url_for(location, **urlparams),
                json_body=urlparams,
            )

        return decorator

    return wrapped


# Note: assumes application/json-compatible media type
def ok(func):
    @wraps(func)
    def decorator(req, params, config):
        return Response(status=200, json_body=func(req, params, config))

    return decorator
