import logging
from functools import wraps
from webob.exc import HTTPUnprocessableEntity
import jsonschema
from jsonschema import RefResolver, RefResolutionError, ValidationError

logger = logging.getLogger(__name__)


def validate(schemas, error_schema=None, query=None, request=None, response=None):
    def decorator(func):
        @wraps(func)
        def _validate(req, params, config=None):
            resolver = RefResolver("", "", store=schemas)

            if not query is None:
                _json_validate(req.params, query, resolver)

            if not request is None:
                _json_validate(req.json_body, request, resolver)

            res = func(req, params, config)

            if not response is None:
                if res.status_code >= 200 and res.status_code < 300:
                    _json_validate(res.json_body, response, resolver)
                elif res.status_code >= 400 and res.status_code < 600:
                    if not error_schema is None:
                        _json_validate(res.json_body, error_schema, resolver)

            return res

        return _validate

    return decorator


def validate_query(url, schemas, error_schema=None):
    return validate(query=url, schemas=schemas, error_schema=error_schema)


def validate_request(url, schemas, error_schema=None):
    return validate(request=url, schemas=schemas, error_schema=error_schema)


def validate_response(url, schemas, error_schema=None):
    return validate(response=url, schemas=schemas, error_schema=error_schema)


def _json_validate(instance, url, resolver):
    try:
        schema = resolver.resolve_from_url(url)
    except RefResolutionError as e:
        raise ref_resolution_error(e)

    try:
        jsonschema.validate(instance, schema)
    except ValidationError as e:
        raise validation_error(e)


def ref_resolution_error(e):
    return HTTPUnprocessableEntity(detail=str(e))


def validation_error(e):
    return HTTPUnprocessableEntity(
        detail=str(e),
        comment="\n".join(
            str(e_) for e_ in sorted(e.context, key=lambda x: x.schema_path)
        ),
    )
