import json
import sys
import csv
from functools import wraps

import click
from dotted.collection import DottedDict

from .api import load_config, save_config, get_manager, filter_users
from .exceptions import ExitException


VERSION = "1.0.3"

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


def _dict_flat_to_nested(flat_dict, defaults={}):
    """
    Takes a "flat" dictionary, whose keys are of the form "one.two.three".
    It will return a nested dictionary with this content:
    {one: {two: {three: value}}}.

    :param flat_dict: The dictionary to convert to a nested one
    :param defaults: Default values to use if flat_dict does not provide them
    :return: A nested python dictionary
    """
    tmp = DottedDict()
    # values from flat_dict have precedence over default values
    for key, val in defaults.items():
        tmp[key] = val
    for key, val in flat_dict.items():
        # key can be "one.two", so keys with a dot in their name are not
        # permitted, cause they are interpreted ...
        tmp[key] = val
    return tmp.to_python()


@click.group(name="config")
def cli_config():
    """Manage okta-cli configuration"""
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
    """Add, update (etc.) users"""
    pass


@cli_users.command(name="list")
@click.option("-m", "--match", 'matches', multiple=True)
@click.option("-p", "--partial", is_flag=True,
              help="Accept partial matches for match queries.")
@click.option("-f", "--filter", 'api_filter', default="")
@click.option("-s", "--search", 'api_search', default="")
@_command_wrapper
def users_list(matches, partial, api_filter, api_search):
    users = okta_manager.list_users(
            filter_query=api_filter,
            search_query=api_search)
    filters_dict = {k: v for k, v in map(lambda x: x.split("="), matches)}
    return list(filter_users(users, filters=filters_dict, partial=partial))


@cli_users.command(name="update")
@click.argument('id')
@click.option('-s', '--set', 'set_fields', multiple=True)
@_command_wrapper
def users_update(id, set_fields):
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    nested_dict = _dict_flat_to_nested(fields_dict)
    return okta_manager.update_user(id, **nested_dict)


@cli_users.command(name="add")
@click.option('-s', '--set', 'set_fields', multiple=True)
@click.option('-r', '--read-csv', help="Read from CSV file", default=None)
@click.option('-a', '--activate/--no-activate',
              help="Set 'activation' flag, see Okta API docs")
@click.option('-p', '--provider/--no-provider',
              help="Set 'provider' flag, see Okta API docs")
@click.option('-n', '--nextlogin/--no-nextlogin',
              help="Set 'nextLogin' to 'changePassword', see Okta API docs")
@_command_wrapper
def users_update(set_fields, read_csv, activate, provider, nextlogin):
    # first use and clean the fields dict from the command line
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    # query parameters
    params = {}
    # set the flags
    if activate:
        params['activate'] = str(activate).upper()
    if provider:
        params['provider'] = str(provider).upper()
    if nextlogin:
        params['nextlogin'] = "changePassword"
    # when reading from csv, we iterate
    if read_csv:
        added = []
        with open(read_csv, "r", encoding="utf-8") as infile:
            dr = csv.DictReader(infile)
            for row in dr:
                final_dict = _dict_flat_to_nested(
                    row, defaults=fields_dict)
                added.append(okta_manager.add_user(params, **final_dict))
        return added
    # when creating directly, we don't :)
    else:
        final_dict = _dict_flat_to_nested(fields_dict)
        return okta_manager.add_user(params, **final_dict)


@click.group()
def cli():
    """
    Okta CLI helper.

    See subcommands for help: "okta-cli users --help" etc.

    If in doubt start with: "okta-cli config new --help"
    """
    pass


@cli.command(name="version")
def cli_version():
    """Prints version number and exit"""
    print(VERSION)


cli.add_command(cli_config)
cli.add_command(cli_users)
