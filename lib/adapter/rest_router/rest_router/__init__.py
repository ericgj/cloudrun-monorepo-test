import sys
import logging
import traceback as tb

import webob
from webob.exc import HTTPNotFound, HTTPError, HTTPInternalServerError
from .api import Api, Resource  # noqa

logger = logging.getLogger("rest_api")


def current_traceback():
    return tb.format_list(tb.extract_tb(sys.exc_info()[2]))


def wsgi(app):
    def _wsgi(environ, start_response):
        req = webob.Request(environ)
        res = app(req)
        return res(environ, start_response)

    return _wsgi


def dispatch_multiple(apis):
    def _dispatch(request):
        iter = (api for api in apis if api.matches_start(request.path))

        for api in iter:
            try:
                request.url_for = _url_for(api).__get__(request)
                handler = api.match(request.method, request.path)
                return handler(request, api.config)

            except HTTPNotFound:
                continue

            except HTTPError as e:
                logger.error(str(e))
                logger.debug("\n".join(current_traceback()))
                return e

            except Exception as e:
                errstr = str(e)
                tbstr = "\n".join(current_traceback())
                logger.error(errstr)
                logger.debug(tbstr)
                return HTTPInternalServerError(detail=errstr, comment=tbstr)

        return HTTPNotFound()

    return _dispatch


def dispatch(api):
    def _dispatch(request):
        try:
            request.url_for = _url_for(api).__get__(request)
            handler = api.match(request.method, request.path)
            return handler(request, api.config)

        except HTTPError as e:
            logger.error(str(e))
            logger.debug("\n".join(current_traceback()))
            return e

        except Exception as e:
            errstr = str(e)
            tbstr = "\n".join(current_traceback())
            logger.error(errstr)
            logger.debug(tbstr)
            return HTTPInternalServerError(detail=errstr, comment=tbstr)

    return _dispatch


def _url_for(api):
    def _url_for_method(req, key, query={}, **kwargs):
        params = {("%s_id" % api.name): api.id}
        params.update(kwargs)
        return api.url_for(req, key, query={}, **params)

    return _url_for_method
