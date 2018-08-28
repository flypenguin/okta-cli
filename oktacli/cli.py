import json
import sys
from functools import wraps

import click

from .api import load_config, save_config, get_manager
from .exceptions import ExitException


okta_manager = None
config = None


def _check_configured(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global okta_manager
        global config
        try:
            okta_manager = get_manager()
            func(*args, **kwargs)
        except ExitException as e:
            print("ERROR: {}".format(str(e)))
            sys.exit(-1)
    return wrapper


@click.group(name="config")
def cli_config():
    pass


@cli_config.command(name="new")
@click.option("-n", "--name", required=True, prompt=True,
              help="Name of the configuration to add.")
@click.option("-u", "--url", required=True, prompt=True,
              help="The base URL of Okta, e.g. 'https://my.okta.com'.")
@click.option("-t", "--token", required=True, prompt=True,
              help="The API token to use")
def config_new(name, url, token):
    global config
    try:
        config = load_config()
    except ExitException:
        config = dict(
                profiles={}
        )
    config["profiles"][name] = dict(
            url=url,
            token=token,
    )
    save_config(config)
    print("Profile '{}' added.".format(name))


@cli_config.command(name="list")
def config_list():
    global config
    config = load_config()
    for name, conf in config["profiles"].items():
        print("{}  {}  {}".format(name, conf["url"], "*"*3+conf["token"][38:]))


@click.group()
def cli_std():
    pass


@cli_std.command(name="list-users")
@_check_configured
def std_list_users():
    print(json.dumps(okta_manager.list_users(), indent=2, sort_keys=True))


@click.group()
def cli():
    pass


cli.add_command(cli_config)
cli.add_command(std_list_users)
