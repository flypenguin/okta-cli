from setuptools import setup

setup(
    name="okta-cli",
    version="0.1",
    py_modules=[],
    install_requires=[
        "appdirs",
        "click",
        "requests",
    ],
    entry_points="""
        [console_scripts]
        okta-cli=oktacli:cli
    """
)
