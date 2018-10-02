import io

from setuptools import setup


BASE_URL = "https://github.com/CognotektGmbH/okta-cli"
VERSION = "1.0.0"

#long_description = (
#    io.open('DESCRIPTION.rst', encoding='utf-8').read() + '\n'
#)

setup(
    name="okta-cli",
    version=VERSION,
    description="An Okta CLI tool to perform routine tasks more quickly. "
                "Work in progress :) . "
                "More information available on the project's GitHub page.",
    #long_description=long_description,
    url=BASE_URL,
    download_url=BASE_URL + "/tarball/{}".format(VERSION),
    py_modules=[],
    install_requires=[
        "appdirs",
        "click",
        "requests",
        "dotted",
    ],
    entry_points="""
        [console_scripts]
        okta-cli=oktacli:cli
    """
)
