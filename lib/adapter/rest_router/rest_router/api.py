import re

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from itertools import chain
from functools import reduce

from webob.exc import HTTPNotFound


class IncompleteResource(Exception):
    def __init__(self, key, params):
        super(IncompleteResource, self).__init__()
        self.key = key
        self.params = params

    def __str__(self):
        return "Incomplete API resource: %s. Missing parameter(s): %s" % (
            self.key,
            ", ".join(self.params),
        )


class UnknownResource(Exception):
    def __init__(self, key):
        super(UnknownResource, self).__init__()
        self.key = key

    def __str__(self):
        return "Unknown API resource: %s." % (self.key,)


class Api:
    @classmethod
    def root(cls, name="", read=None, config={}):
        return cls([], id=None, name=name, read=read, config=config)

    def __init__(self, resources, id, name="", read=None, config={}):
        self.config = config
        self.id = id
        self.name = name
        root = Resource(name=name, id=id, resources=resources, read=read)
        self._index = index_matchers(compile_resource(root, []))
        self._start = compile_start([name, id])
        self._path_index = dict(compile_paths(root, [], []))

    def match(self, method, path):
        path_len = len(path.strip("/").split("/"))
        candidates = self._index.get((path_len, method), [])
        if len(candidates) == 0:
            raise HTTPNotFound()
        else:
            try:
                return next(match_path(path, candidates))
            except StopIteration:
                raise HTTPNotFound()

    def matches_start(self, path):
        return not self._start.match(path) is None

    def url_for(self, req, key, query={}, **kwargs):
        return req.application_url + self.path_for(key, query, **kwargs)

    def path_for(self, key, query={}, **kwargs):
        try:
            tmpl = self._path_index[key]
        except KeyError:
            raise UnknownResource(key)

        try:
            path = tmpl.format(**kwargs)
        except KeyError as e:
            raise IncompleteResource(key, e.args)

        return path + ("?" + urlencode(query) if query else "")


class Resource:
    def __init__(
        self,
        name,
        id=None,
        list_=None,
        read=None,
        create=None,
        update=None,
        delete=None,
        resources=[],
    ):
        self.name = name
        self.id = id
        self.list_ = list_
        self.read = read
        self.create = create
        self.update = update
        self.delete = delete
        self.resources = resources


class Matcher:
    def __init__(self, length, method, template, func):
        self.length = length
        self.method = method
        self.template = template
        self.func = func

    def __repr__(self):
        return "Matcher(%d, %s, %s, <func>)" % (
            self.length,
            self.method.__repr__(),
            self.template.__repr__(),
        )


class Handler:
    def __init__(self, params, func):
        self.params = params
        self.func = func

    def __call__(self, req, config={}):
        return self.func(req, self.params, config=config)

    def __repr__(self):
        return "Handler(%s, <func>)" % (self.params.__repr__(),)


# Routing implementation


def compile_resource(resource, prefix):
    if resource.id is None:
        return compile_singleton_resource(resource, prefix)
    else:
        return compile_entity_resource(resource, prefix)


def compile_singleton_resource(resource, prefix):
    name = re.escape(resource.name)
    single = compile_collection(prefix, name)
    single_len = len(prefix) + 1

    return (
        (
            [
                Matcher(
                    length=single_len, method="GET", template=single, func=resource.read
                )
            ]
            if resource.read
            else []
        )
        + (
            [
                Matcher(
                    length=single_len,
                    method="POST",
                    template=single,
                    func=resource.update,
                )
            ]
            if resource.update
            else []
        )
        + (
            [
                Matcher(
                    length=single_len,
                    method="DELETE",
                    template=single,
                    func=resource.delete,
                )
            ]
            if resource.delete
            else []
        )
        + list(
            chain.from_iterable(
                [compile_resource(sub, prefix + [name]) for sub in resource.resources]
            )
        )
    )


def compile_entity_resource(resource, prefix):
    id = capture_id(resource.id)
    ancestor_id = capture_ancestor_id(resource.name, resource.id)
    name = re.escape(resource.name)
    (collection, entity) = compile(prefix, name, id)
    collection_len = len(prefix) + 1
    entity_len = len(prefix) + 2

    return (
        (
            [
                Matcher(
                    length=collection_len,
                    method="GET",
                    template=collection,
                    func=resource.list_,
                )
            ]
            if resource.list_
            else []
        )
        + (
            [
                Matcher(
                    length=collection_len,
                    method="POST",
                    template=collection,
                    func=resource.create,
                )
            ]
            if resource.create
            else []
        )
        + (
            [
                Matcher(
                    length=entity_len, method="GET", template=entity, func=resource.read
                )
            ]
            if resource.read
            else []
        )
        + (
            [
                Matcher(
                    length=entity_len,
                    method="POST",
                    template=entity,
                    func=resource.update,
                )
            ]
            if resource.update
            else []
        )
        + (
            [
                Matcher(
                    length=entity_len,
                    method="DELETE",
                    template=entity,
                    func=resource.delete,
                )
            ]
            if resource.delete
            else []
        )
        + list(
            chain.from_iterable(
                [
                    compile_resource(sub, prefix + [name, ancestor_id])
                    for sub in resource.resources
                ]
            )
        )
    )


def index_matchers(matchers):
    def _index(acc, matcher):
        grp = acc.get((matcher.length, matcher.method), [])
        grp.append(matcher)
        acc[(matcher.length, matcher.method)] = grp
        return acc

    return reduce(_index, matchers, {})


def match_path(path, matchers):
    for matcher in matchers:
        m = matcher.template.match(path)
        if m is None:
            continue
        else:
            yield Handler(func=matcher.func, params=m.groupdict())


def capture_id(id):
    return "(?P<id>" + id + ")"


def capture_ancestor_id(name, id):
    return "(?P<" + py_identifier(name) + "_id>" + id + ")"


def py_identifier(s):
    return re.sub("\W|^(?=\d)", "_", s)


def compile(prefix, name, id):
    return (compile_collection(prefix, name), compile_entity(prefix, name, id))


def compile_collection(prefix, name):
    return re.compile("\\/" + "\\/".join(prefix + [name]) + "(?:\\/){0,1}\Z")


def compile_entity(prefix, name, id):
    return re.compile("\\/" + "\\/".join(prefix + [name, id]) + "(?:\\/){0,1}\Z")


def compile_start(prefix):
    return re.compile("\\/" + "\\/".join(prefix))


def compile_paths(resource, prefix, prefix_keys):
    if resource.id is None:
        return compile_singleton_paths(resource, prefix, prefix_keys)
    else:
        return compile_entity_paths(resource, prefix, prefix_keys)


def compile_singleton_paths(resource, prefix, prefix_keys):
    single = "/" + "/".join(prefix + [resource.name])
    key = ".".join([k for (i, k) in enumerate(prefix_keys) if i > 0] + [resource.name])
    return (
        ([("%s.read" % key, single)] if resource.read else [])
        + ([("%s.update" % key, single)] if resource.update else [])
        + ([("%s.delete" % key, single)] if resource.delete else [])
        + list(
            chain.from_iterable(
                [
                    compile_paths(
                        sub, prefix + [resource.name], prefix_keys + [resource.name]
                    )
                    for sub in resource.resources
                ]
            )
        )
    )


def compile_entity_paths(resource, prefix, prefix_keys):
    ancestor_id = "{%s_id}" % py_identifier(resource.name)
    collection = "/" + "/".join(prefix + [resource.name])
    entity = "/" + "/".join(prefix + [resource.name, "{id}"])
    key = ".".join([k for (i, k) in enumerate(prefix_keys) if i > 0] + [resource.name])
    return (
        ([("%s.list" % key, collection)] if resource.list_ else [])
        + ([("%s.create" % key, collection)] if resource.create else [])
        + ([("%s.read" % key, entity)] if resource.read else [])
        + ([("%s.update" % key, entity)] if resource.update else [])
        + ([("%s.delete" % key, entity)] if resource.delete else [])
        + list(
            chain.from_iterable(
                [
                    compile_paths(
                        sub,
                        prefix + [resource.name, ancestor_id],
                        prefix_keys + [resource.name],
                    )
                    for sub in resource.resources
                ]
            )
        )
    )
