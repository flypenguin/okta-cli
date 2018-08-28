import json
import sys
from functools import wraps

import click

from .api import load_config, save_config, get_manager, filter_users
from .exceptions import ExitException


okta_manager = None
config = None


def _command_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global okta_manager
        global config
        try:
            okta_manager = get_manager()
            rv = func(*args, **kwargs)
            if not isinstance(rv, str):
                print(json.dumps(rv, indent=2, sort_keys=True))
            else:
                print(rv)
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


@cli_config.command(name="use-context")
@click.argument("profile-name")
@_command_wrapper
def config_use_context(profile_name):
    global config
    config = load_config()
    if profile_name not in config["profiles"]:
        raise ExitException("Unknown profile name: '{}'.".format(profile_name))
    config["default"] = profile_name
    save_config(config)
    return "Default profile set to '{}'.".format(profile_name)


@cli_config.command(name="current-context")
@_command_wrapper
def config_current_context():
    config = load_config()
    if "default" not in config:
        return "No profile set."
    return "Current profile set to '{}'.".format(config["default"])


@click.group(name="users")
def cli_users():
    pass


@cli_users.command(name="list")
@click.option("-f", "--filter", 'filters', multiple=True)
@click.option("-p", "--partial", is_flag=True,
              help="Accept partial matches for filters.")
@_command_wrapper
def users_list(filters, partial):
    filters_dict = {k: v for k, v in map(lambda x: x.split("="), filters)}
    users = okta_manager.list_users()
    return list(filter_users(users, filters=filters_dict, partial=partial))


@cli_users.command(name="search")
@click.argument("query", nargs=-1)
@_command_wrapper
def users_search(query):
    return okta_manager.search_user(" ".join(query))


@cli_users.command(name="update")
@click.argument('id')
@click.option('-s', '--set', 'set_fields', multiple=True)
@_command_wrapper
def users_update(id, set_fields):
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    return okta_manager.update_user(id, **fields_dict)


@click.group()
def cli():
    pass


cli.add_command(cli_config)
cli.add_command(cli_users)
