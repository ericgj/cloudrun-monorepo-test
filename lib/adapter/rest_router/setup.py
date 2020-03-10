from setuptools import setup

def version():
    with open("VERSION") as f:
        return f.read().strip()

setup(
  name = "rest_router",
  version = version(),
  author = "Eric Gjertsen",
  author_email = "egjertsen@ert.com",
  description = "A REST-oriented WSGI router built on webob",
  license = "MIT",
  keywords = "WSGI REST web router",
  packages = ["rest_router"],
  install_requires = [
    "WebOb<1.9.0",
    "jsonschema<3.3.0"
  ]
)

