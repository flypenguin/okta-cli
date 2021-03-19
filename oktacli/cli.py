import json
import logging
import sys
import collections
import csv
import re
import traceback
from datetime import datetime as dt
from functools import wraps
from os.path import splitext, join, isdir
from os import mkdir
from concurrent.futures import ThreadPoolExecutor, as_completed

import click
import yaml
from requests import RequestException
from dotted.collection import DottedDict, DottedCollection
from requests.exceptions import HTTPError as RequestsHTTPError
from openpyxl import load_workbook

from .api import load_config
from .api import save_config
from .api import get_manager
from .api import filter_dicts
from .api import get_config_file

from .okta import REST
from .okta import OktaAPIError
from .exceptions import ExitException

VERSION = "17.2.0"

# global constants
TABLE_MAX_FIELD_LENGTH = None


# variables
okta_manager = None
config = None

# https://is.gd/T1enMM
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def _print_table_from(print_obj, fields, *, max_len=None):
    if isinstance(print_obj, dict):
        print_obj = [print_obj]
    arr = DottedCollection.factory(print_obj)
    col_lengths = []
    if fields is None:
        fields = [x for x in arr[0].keys()]
    else:
        fields = fields.split(",")
    for col in fields:
        try:
            col_lengths.append(max([len(str(DottedDict(item)[col]))
                                    for item in arr if col in item]))
        except ValueError:
            # we don't have a "col" field or it's not used.
            # and we can't use 0 as width cause this will cause a weird
            # exception
            col_lengths.append(1)
            print(f"WARNING: field {col} either never filled or non-existant.",
                  file=sys.stderr)
    # enforce max field length to print
    if max_len is not None:
        col_lengths = [min(max_len, l) for l in col_lengths]
    for row in arr:
        for col_idx, col in enumerate(fields):
            val = str(row[col]) if col in row else ""
            if max_len and len(val) > max_len:
                val = val[:max_len] + "..."
            print(f"{val:{col_lengths[col_idx]}}  ", end="")
        print("")


def _dump_csv(print_obj, *, dialect=None, out=sys.stdout, fields=None):
    if isinstance(print_obj, dict):
        print_obj = [print_obj]
    # extract all the column fields from the result set
    tmp_dict = {}
    for obj in print_obj:
        tmp_dict.update(dict.fromkeys(_dict_get_dotted_keys(obj)))
    fieldlist = list(sorted(tmp_dict.keys()))
    # iterate through the list and print it
    writer = csv.DictWriter(out,
                            fieldnames=fieldlist,
                            extrasaction='ignore',
                            dialect=dialect)
    writer.writeheader()
    for obj in print_obj:
        writer.writerow(_dict_nested_to_flat(obj))


def _command_wrapper(func):
    @wraps(func)
    @click.option('-v', '--verbose', 'verbosity',
                  count=True, default=0,
                  help="Increase verbosity (-vvvvv for full DEBUG logging)")
    def wrapper(*args, **kwargs):
        global okta_manager
        global config
        # configure logging, use levels as defined here: https://is.gd/G2vcgB
        # we need to pop it cause otherwise it will lead to parameter errors
        # on the execution functions
        verb = kwargs.pop("verbosity")
        if verb:
            verb = max(10, 60 - verb * 10)
            print("log level: ", verb)
            logging.basicConfig(level=verb)
            logging.getLogger("cli.requests.packages.urllib3").setLevel(verb)
            # from here: https://thomas-cokelaer.info/blog/?p=1577
            if verb <= 10:
                from http.client import HTTPConnection
                HTTPConnection.debuglevel = 1
        try:
            okta_manager = get_manager()
            rv = func(*args, **kwargs)
            if not isinstance(rv, str):
                if kwargs.get("print_json", False) is True:
                    print(json.dumps(rv, indent=2, sort_keys=True,
                                     ensure_ascii=False))
                elif kwargs.get("print_yaml", False) is True:
                    print(yaml.safe_dump(rv, indent=2, encoding=None, allow_unicode=True))
                elif kwargs.get("print_csv", False) is True:
                    _dump_csv(rv, dialect=kwargs['csv_dialect'])
                elif "output_fields" in kwargs and len(rv) > 0:
                    max_len = kwargs.get("max_len", None)
                    _print_table_from(rv, kwargs["output_fields"], max_len=max_len)
                else:
                    # default fallback setting - print json.
                    print(json.dumps(rv, indent=2, sort_keys=True))
            else:
                print(rv)
        except ExitException as e:
            print("ERROR: {}".format(str(e)), file=sys.stderr)
            sys.exit(-1)
        except RequestException as e:
            print(f"COMMUNICATION_ERROR: {str(e)}", file=sys.stderr)
            sys.exit(-1)
        except OktaAPIError as e:
            print(f"OKTA_API_ERROR: {e.error_code}: {str(e)}")
            for cause in e.error_causes:
                for hdg, txt in cause.items():
                    print(f"{hdg}: {txt}")
            sys.exit(-3)
        except Exception as e:
            print("".join(traceback.format_exc()), file=sys.stderr)
            print(f"""
*****************************************************************************
CRITICAL_ERROR: {str(type(e))}

Please report at the issues page with details of what you did. Thank you!
-> https://git.io/JJYqi
*****************************************************************************
""", file=sys.stderr)
            sys.exit(-2)

    return wrapper


def _output_type_command_wrapper(default_fields):
    def _output_type_command_wrapper_inner(func):
        @wraps(func)
        @click.option("-j", "--json", 'print_json', is_flag=True, default=False,
                      help="Print raw JSON output")
        @click.option("-y", "--yaml", 'print_yaml', is_flag=True, default=False,
                      help="Print raw YAML output")
        @click.option("--csv", "print_csv", is_flag=True, default=False,
                      help="Print output as CSV format. Will ignore "
                           "--output-fields parameter if set")
        @click.option("--csv-dialect", default='excel',
                      help="Use this CSV dialect with CSV output")
        @click.option("--output-fields",
                      default=default_fields,
                      help="Override default fields in table format")
        @click.option("--colwidth",
                      default=TABLE_MAX_FIELD_LENGTH, type=int,
                      help="Limit column width; "
                           f"default: {TABLE_MAX_FIELD_LENGTH or 'unlimited'}")
        @_command_wrapper
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return _output_type_command_wrapper_inner


def _dict_flat_to_nested(flat_dict, defaults=None):
    """
    Takes a "flat" dictionary, whose keys are of the form "one.two.three".
    It will return a nested dictionary with this content:
    {one: {two: {three: value}}}.

    :param flat_dict: The dictionary to convert to a nested one
    :param defaults: Default values for nested dict in (with flat (!) keys)
    :return: A nested python dictionary
    """
    tmp = DottedDict()
    if defaults is None:
        defaults = {}
    for key, val in defaults.items():
        tmp[key] = val
    for key, val in flat_dict.items():
        tmp[key] = val
    return tmp.to_python()


# from here: https://stackoverflow.com/a/6027615
def _dict_nested_to_flat(nested_dict, parent_key="", sep="."):
    """
    Takes a nested dictionary and converts it into a flat one.

    Like this: `{"one": {"two": "three}}` will become `{"one.two": "three"}`

    :param nested_dict:
    :param parent_key:
    :param sep:
    :return:
    """
    items = []
    for k, v in nested_dict.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(_dict_nested_to_flat(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _dict_get_dotted_keys(dict_inst, pre_path=""):
    rv = []
    for key in dict_inst.keys():
        tmp = dict_inst[key]
        if isinstance(tmp, dict):
            rv += _dict_get_dotted_keys(tmp, pre_path + key + ".")
        else:
            rv.append(pre_path + key)
    return rv


def _okta_retrieve(thing, possible_id,
                   *,
                   selector=None,
                   **call_params):
    """Returns anything between nothing and a list of items"""
    if possible_id is not None:
        try:
            # let's just return this if possible. also, no (!) "params" parameter
            # the params parameter contains the query, which we don't need here.
            return okta_manager.call_okta(f"/{thing}/{possible_id}", REST.get)
        except OktaAPIError as e:
            pass

    # we're still here? so let's continue.
    params = call_params or {}
    things = okta_manager.call_okta(f"/{thing}", REST.get, params=params)
    if isinstance(things, list):
        if selector:
            things = list(filter(selector, things))
    return things


def _okta_get(thing, possible_id,
              **kwargs):
    things = _okta_retrieve(thing, possible_id, **kwargs)
    if isinstance(things, list):
        if len(things) > 1:
            raise ExitException(f"Name for {thing} must be unique. "
                                f"(found {len(things)} matches).")
        elif len(things) == 0:
            raise ExitException(f"No matching {thing} found.")
        # must be here - ouside of this 'if' things can (and sometimes will)
        # be a dict
        things = things[0]
    return things


def _selector_profile_find(field, value):
    lower_value = value.lower()
    return lambda x: x["profile"][field].lower().find(lower_value) != -1


def _selector_profile_find_group(field, value):
    lower_value = value.lower()
    return lambda x: (x["profile"][field].lower().find(lower_value) != -1 and
                      x["type"] == "OKTA_GROUP")


def _selector_field_find(field, value):
    lower_value = value.lower()
    return lambda x: x[field].lower().find(lower_value) != -1


@click.group(name="config")
def cli_config():
    """Manage okta-cli configuration"""
    pass


@cli_config.command(name="new", context_settings=CONTEXT_SETTINGS)
@click.option("-n", "--name", required=True, prompt=True,
              help="Name of the configuration to add.")
@click.option("-u", "--url", required=True, prompt=True,
              help="The base URL of Okta, e.g. 'https://my.okta.com'.")
@click.option("-t", "--token", required=True, prompt=True,
              help="The API token to use")
def config_new(name, url, token):
    """
    Create a new configuration profile
    """
    global config
    try:
        config = load_config()
    except ExitException:
        config = dict(profiles={})
    config["profiles"][name] = dict(url=url, token=token)
    save_config(config)
    print("Profile '{}' added.".format(name))


@cli_config.command(name="list", context_settings=CONTEXT_SETTINGS)
def config_list():
    """List all configuration profiles"""
    global config
    config = load_config()
    for name, conf in config["profiles"].items():
        print("{}  {}  {}".format(name, conf["url"],
                                  "*" * 3 + conf["token"][-4:]))


@cli_config.command(name="use-context", context_settings=CONTEXT_SETTINGS)
@click.argument("profile-name")
@_command_wrapper
def config_use_context(profile_name):
    """
    Set a config profile as default profile
    """
    global config
    config = load_config()
    if profile_name not in config["profiles"]:
        raise ExitException("Unknown profile name: '{}'.".format(profile_name))
    config["default"] = profile_name
    save_config(config)
    return "Default profile set to '{}'.".format(profile_name)


@cli_config.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument("profile-name")
@_command_wrapper
def config_delete(profile_name):
    """
    Delete a config profile
    """
    global config
    rv = []
    config = load_config()
    if profile_name not in config["profiles"]:
        raise ExitException("Unknown profile name: '{}'.".format(profile_name))
    del config["profiles"][profile_name]
    rv.append("Profile '{}' deleted.".format(profile_name))
    if config["default"] == profile_name:
        if len(config["profiles"]):
            new_default = list(config["profiles"].keys())[0]
            config["default"] = new_default
            rv.append("New default profile: {}".format(new_default))
        else:
            del config["default"]
            rv.append("No more profiles left.")
    save_config(config)
    return "\n".join(rv)


@cli_config.command(name="file", context_settings=CONTEXT_SETTINGS)
@_command_wrapper
def config_file():
    """
    Print the locations of the configuration file
    """
    return get_config_file()


@cli_config.command(name="current-context", context_settings=CONTEXT_SETTINGS)
@_command_wrapper
def config_current_context():
    """
    Print the current default profile
    """
    global config
    config = load_config()
    if "default" not in config:
        return "No profile set."
    return "Current profile set to '{}'.".format(config["default"])


@click.group(name="pw")
def cli_pw():
    """Manage passwords"""
    pass


@cli_pw.command(name="reset", context_settings=CONTEXT_SETTINGS)
@click.argument("login-or-id")
@click.option("-n", "--no-email", is_flag=True)
@_command_wrapper
def pw_reset(login_or_id, no_email):
    """Reset the password of a user"""
    return okta_manager.reset_password(login_or_id, send_email=not no_email)


@cli_pw.command(name="expire", context_settings=CONTEXT_SETTINGS)
@click.argument("login-or-id")
@click.option("-t", "--temp-password", is_flag=True)
@_command_wrapper
def pw_expire(login_or_id, temp_password):
    """Expire the password of a user"""
    return okta_manager.expire_password(login_or_id,
                                        temp_password=temp_password)


@cli_pw.command(name="set", context_settings=CONTEXT_SETTINGS)
@click.argument("login-or-id")
@click.option("-s", "--set", "set_password", help="set password to this")
@click.option("-g", "--generate", help="generate a random password",
              is_flag=True)
@click.option("--expire/--no-expire", help="expire password (default: yes)",
              is_flag=True, default=True)
@click.option("-l", "--language", help="use a word list from this language",
              default="en")
@click.option("-m", "--min-length", help="minimal password length", type=int,
              default=14)
@_command_wrapper
def pw_set(login_or_id, set_password, generate, expire, language, min_length):
    """Set a user's password"""
    # import here cause it takes time it seems ...
    from .pwgen import generate_password
    default_password_length = 5
    num_words = max(3, int(min_length / default_password_length + 3))
    if generate:
        words = generate_password(num_words, lang=language)
        for i in range(3, num_words):
            set_password = " ".join(words[:i])
            if len(set_password) >= min_length:
                break
    elif not set_password:
        raise ExitException("Either use -s or -g!")
    profile_dict = {"credentials.password.value": set_password}
    nested_dict = _dict_flat_to_nested(profile_dict)
    okta_manager.update_user(login_or_id, nested_dict)
    if expire:
        okta_manager.expire_password(login_or_id, temp_password=False)
    rv = (
        "PASSWORD" +
        ("_EXPIRED" if expire else "") +
        f": {set_password}"
    )
    return rv


@click.group(name="groups")
def cli_groups():
    """Group operations"""
    pass


@cli_groups.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--filter", 'filter_query', default="")
@click.option("-q", "--query", 'q_query', default="")
@click.option("-a", "--all", "all_groups", help="Include APP_GROUPs in list")
@_output_type_command_wrapper("id,type,profile.name")
def groups_list(partial_name, filter_query, q_query, all_groups, **kwargs):
    """List all defined groups"""
    params = {}
    if filter_query:
        params["filter"] = filter_query
    if q_query:
        params["q"] = q_query
    selector = None
    if partial_name:
        selector = _selector_profile_find("name", partial_name)
    rv = _okta_retrieve("groups", None, selector=selector, **params)
    if not all_groups:
        rv = list(filter(lambda x: x["type"] == "OKTA_GROUP", rv))
    return rv


@cli_groups.command(name="add", context_settings=CONTEXT_SETTINGS)
@click.option("-n", "--name", required=True)
@click.option("-d", "--description", default=None)
@_output_type_command_wrapper("id,type,profile.name")
def groups_add(name, description, **kwargs):
    """Create a new group"""
    new_group = {"profile": {"name": name, "description": description}}
    return okta_manager.call_okta(f"/groups", REST.post, body_obj=new_group)


@cli_groups.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@_output_type_command_wrapper("id,type,profile.name")
def groups_delete(name_or_id, **kwargs):
    """Delete a group

    When you give a name a name substring match will be performed. If more
    than one group matches execution will be aborted.
    """
    group = _okta_get("groups", name_or_id,
                      selector=_selector_profile_find_group("name", name_or_id))
    group_id = group['id']
    okta_manager.call_okta_raw(f"/groups/{group_id}", REST.delete)
    return f"group {group_id} deleted"


@cli_groups.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@_output_type_command_wrapper("id,type,profile.name")
def groups_get(name_or_id, **kwargs):
    """Print only one group"""
    return _okta_get("groups", name_or_id,
                     selector=_selector_profile_find_group("name", name_or_id))


@cli_groups.command(name="adduser", context_settings=CONTEXT_SETTINGS)
@click.option("-g", "--group", required=True,
              metavar="GID-OR-UNIQUE",
              help="The group ID to add a user to")
@click.option("-u", "--user", required=True,
              metavar="EXACT-MATCH",
              help="The user ID to add to the group, either the user id or "
                   "an exact (!) match of the --user-lookup-field")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Matching is done against this profile field; default: 'login'.")
@_command_wrapper
def groups_adduser(group, user, user_lookup_field, **kwargs):
    """
    Adds a user to a group.

    You can use any Okta profile field to select users by using "-f".
    """
    group = _okta_get("groups", group,
                      selector=_selector_profile_find_group("name", group))
    group_id = group["id"]
    group_name = group["profile"]["name"]
    user = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user["id"]
    user_login = user["profile"]["login"]
    okta_manager.call_okta_raw(
        f"/groups/{group_id}/users/{user_id}",
        REST.put)
    return f"User {user_id} ({user_login}) added to group {group_id} ({group_name})"


@cli_groups.command(name="removeuser", context_settings=CONTEXT_SETTINGS)
@click.option("-g", "--group", required=True,
              metavar="GID-OR-UNIQUE",
              help="The group ID to add a user to")
@click.option("-u", "--user", required=True,
              metavar="ID-or-FIELDVALUE",
              help="The user ID to add to the group")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@_command_wrapper
def groups_removeuser(group, user, user_lookup_field, **kwargs):
    """
    Removes a user from a group.

    Note that you must use Okta's user and group IDs.
    """
    group = _okta_get("groups", group,
                      selector=_selector_profile_find_group("name", group))
    group_id = group["id"]
    user = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user["id"]
    user_login = user["profile"]["login"]
    group_name = group["profile"]["name"]
    okta_manager.call_okta_raw(
        f"/groups/{group_id}/users/{user_id}",
        REST.delete)
    return f"User {user_id} ({user_login}) removed from group {group_id} ({group_name})"


@cli_groups.command(name="users", context_settings=CONTEXT_SETTINGS)
@click.argument("id-or-unique")
@_output_type_command_wrapper("id,profile.login,profile.firstName,"
                              "profile.lastName,profile.email")
def groups_users(id_or_unique, **kwargs):
    """List all users in a group"""
    group = _okta_get("groups", id_or_unique,
                      selector=_selector_profile_find_group("name", id_or_unique))
    group_id = group["id"]
    rv = okta_manager.call_okta(f"/groups/{group_id}/users", REST.get)
    rv.sort(key=lambda x: x["profile"]["login"].lower())
    return rv


@cli_groups.command(name="clear", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@click.option("-i", "--id", 'use_id', is_flag=True, default=False,
              help="Use Okta group ID instead of the group name")
@_command_wrapper
def groups_clear(name_or_id, use_id):
    """Remove all users from a group.

    This can take a while if the group is big."""
    group = _okta_get("groups", name_or_id,
                      selector=_selector_profile_find_group("name", name_or_id))
    group_id = group["id"]
    group_name = group["profile"]["name"]
    users = okta_manager.call_okta(f"/groups/{group_id}/users", REST.get)
    for user in sorted(users, key=lambda x: x["profile"]["login"]):
        user_id = user['id']
        user_login = user['profile']['login']
        print(f"Removing user {user_login} ... ", file=sys.stderr, end="")
        path = f"/groups/{name_or_id}/users/{user_id}"
        okta_manager.call_okta_raw(path, REST.delete)
        print("ok", file=sys.stderr)
    return f"All users removed from group {group_id} ({group_name})"


@click.group(name="apps")
def cli_apps():
    """Application operations"""
    pass


APP_DEFAULTS = {
    "bookmark": (
        ("sa.requestIntegration", "false"),
    ),
}

APP_TYPES = [
    "bookmark",
    "template_basic_auth",
    "template_swa",
    "template_swa3field",
    "template_sps",
    "oidc_client",
    "template_wsfed",
]

SIGNON_TYPES = [
    "BOOKMARK",
    "BASIC_AUTH",
    "BROWSER_PLUGIN",
    "SECURE_PASSWORD_STORE",
    "SAML_2_0",
    "WS_FEDERATION",
    "AUTO_LOGIN",
    "OPENID_CONNECT",
    "Custom",
]

SIGNON_DEFAULTS = {
    "bookmark": "BOOKMARK",
    "template_basic_auth": "BASIC_AUTH",
    "template_swa": "BROWSER_PLUGIN",
    "template_swa3field": "BROWSER_PLUGIN",
    "template_sps": "SECURE_PASSWORD_STORE",
    "oidc_client": "OPENID_CONNECT",
    "template_wsfed": "WS_FEDERATION",
}

PREF_SHORTCUTS = (
    ("sa", "settings.app"),
    ("v", "visibility"),
    ("f", "features"),
    ("c", "credentials"),
)


def _unshorten_app_settings(setting_item):
    key, val = setting_item
    for short, long in PREF_SHORTCUTS:
        key = re.sub(f"^{short}\.", long + ".", key)
    return key, val


@cli_apps.command(name="add", context_settings=CONTEXT_SETTINGS)
@click.option("-n", "--name",
              help="The application name - Okta-internal field, NOT the name "
                   "displayed in the Okta UI!",
              type=click.Choice(APP_TYPES), default=None)
@click.option("-m", "--signonmode",
              help="Sign on mode of the app, you should not need to set this "
                   "manually",
              type=click.Choice(SIGNON_TYPES), default=None)
@click.option("-l", "--label", help="The application label")
@click.option("-s", "--set", "set_fields",
              help="Set app parameter. You can use prefix shortcuts "
                   "(sa=settings.apps, v=visibility, "
                   "f=features, c=credentials)",
              multiple=True)
@_command_wrapper
def apps_add(name, signonmode, label, set_fields):
    """Add a new application

    See https://is.gd/E3mFYj for details.

    \b
    EXAMPLE: Add a bookmark app:
    okta-cli apps add -n bookmark -l my_bookmark -s sa.url=http://my.url
    """
    settings = list(APP_DEFAULTS.get(name, []))
    settings += [x.split("=", 1) for x in set_fields]
    settings = list(map(_unshorten_app_settings, settings))
    new_app = dict(settings)
    if name and name in SIGNON_DEFAULTS:
        signonmode = SIGNON_DEFAULTS[name]
    for check, setme in \
            ((name, "name"), (label, "label"), (signonmode, "signOnMode")):
        if check is not None:
            new_app[setme] = check
    new_app = _dict_flat_to_nested(new_app)
    return okta_manager.call_okta("/apps", REST.post, body_obj=new_app)


@cli_apps.command(name="activate", context_settings=CONTEXT_SETTINGS)
@click.argument("label-or-id")
@_command_wrapper
def apps_activate(label_or_id):
    """Activate an application"""
    app = _okta_get("apps", label_or_id,
                    selector=_selector_field_find("label", label_or_id))
    app_id = app['id']
    app_label = app["label"]
    path = f"/apps/{app_id}/lifecycle/activate"
    okta_manager.call_okta_raw(path, REST.post)
    return f"application {app_id} ({app_label}) activated"


@cli_apps.command(name="deactivate", context_settings=CONTEXT_SETTINGS)
@click.argument("label-or-id")
@_command_wrapper
def apps_deactivate(label_or_id):
    """Deactivate an application

    Must be done before deletion"""
    app = _okta_get("apps", label_or_id,
                    selector=_selector_field_find("label", label_or_id))
    app_id = app['id']
    app_label = app["label"]
    path = f"/apps/{app_id}/lifecycle/deactivate"
    okta_manager.call_okta_raw(path, REST.post)
    return f"application {app_id} ({app_label}) deactivated"


@cli_apps.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument("label-or-id")
@_command_wrapper
def apps_delete(label_or_id):
    """Delete an application"""
    app = _okta_get("apps", label_or_id,
                    selector=_selector_field_find("label", label_or_id))
    app_id = app['id']
    app_label = app["label"]
    okta_manager.call_okta_raw(f"/apps/{app_id}", REST.delete)
    return f"application {app_id} ({app_label}) deleted"


@cli_apps.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--filter", 'filter_query', default="", metavar="EXPRESSION")
@click.option("-q", "--query", 'q_query', default="")
@_output_type_command_wrapper("id,label")
def apps_list(partial_name, filter_query, q_query, **kwargs):
    """List all defined applications. If you give an optional command line
    argument, the apps are filtered by name using this string.

    \b
    Examples:
    okta-cli apps list
    okta-cli apps list office       # 'full text' search, slow
    okta-cli apps list -q Office    # 'starts with' search, fast
    """
    params = {}
    if filter_query:
        params["filter"] = filter_query
    if q_query:
        params["q"] = q_query
    selector = None
    if partial_name:
        selector = _selector_field_find("label", partial_name)
    rv = _okta_retrieve("apps", partial_name, selector=selector, **params)
    rv.sort(key=lambda x: x["label"].lower())
    return rv


@cli_apps.command(name="users", context_settings=CONTEXT_SETTINGS)
@click.argument("app")
@_output_type_command_wrapper("status,id,credentials.userName,")
def apps_users(app, **kwargs):
    """List all users for an application"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    app_id = app["id"]
    rv = okta_manager.call_okta(f"/apps/{app_id}/users", REST.get)
    rv.sort(key=lambda x: x["credentials"]["userName"])
    return rv


@cli_apps.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@_output_type_command_wrapper("id,name,label")
def apps_get(partial_name, **kwargs):
    """Retrieves information about one specific application"""
    app = _okta_get("apps", partial_name,
                    selector=_selector_field_find("label", partial_name))
    return app


@cli_apps.command(name="getuser", context_settings=CONTEXT_SETTINGS)
@click.option("-a", "--app", "app")
@click.option("-u", "--user", "user")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@_output_type_command_wrapper("id,credentials.userName,scope,status,syncState")
def apps_getuser(app, user, user_lookup_field, **kwargs):
    """Retrieves information about one specific assigned user of an application"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    user = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user["id"]
    app_id = app['id']
    return okta_manager.call_okta(f"/apps/{app_id}/users/{user_id}", REST.get)


@cli_apps.command(name="adduser", context_settings=CONTEXT_SETTINGS)
@click.option("-a", "--app", "app", required=True)
@click.option("-u", "--user", "user", required=True)
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@click.option('-s', '--set', 'set_fields', multiple=True)
@_output_type_command_wrapper("id,credentials.userName,scope,status,syncState")
def apps_adduser(app, user, user_lookup_field, set_fields, **kwargs):
    """Add a user to an application"""
    appuser = {k: v for k, v in map(lambda x: x.split("=", 1), set_fields)}
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    user = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user["id"]
    app_id = app['id']

    appuser["id"] = user_id
    appuser = _dict_flat_to_nested(appuser)
    return okta_manager.call_okta(f"/apps/{app_id}/users", REST.post, body_obj=appuser)


@cli_apps.command(name="removeuser", context_settings=CONTEXT_SETTINGS)
@click.option("-a", "--app", "app")
@click.option("-u", "--user", "user")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@_command_wrapper
def apps_removeuser(app, user, user_lookup_field, **kwargs):
    """Rempoves a user from an application"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    user = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user["id"]
    user_login = user["profile"]["login"]
    app_id = app['id']
    app_label = app["label"]
    okta_manager.call_okta_raw(f"/apps/{app_id}/users/{user_id}", REST.delete)
    return f"User {user_id} ({user_login}) removed from app {app_id} ({app_label})"


@cli_apps.command(name="addgroup", context_settings=CONTEXT_SETTINGS)
@click.option("-a", "--app", "app")
@click.option("-g", "--group", "group")
@_output_type_command_wrapper(None)
def apps_addgroup(app, group, **kwargs):
    """Assigns a group to this app"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    group = _okta_get("groups", group,
                      selector=_selector_profile_find_group("name", group))
    group_id = group["id"]
    app_id = app['id']
    rv = okta_manager.call_okta(f"/apps/{app_id}/groups/{group_id}", REST.put)
    return rv


@cli_apps.command(name="removegroup", context_settings=CONTEXT_SETTINGS)
@click.option("-a", "--app", "app")
@click.option("-g", "--group", "group")
@_command_wrapper
def apps_removegroup(app, group, **kwargs):
    """Removes a group association from an app"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    group = _okta_get("groups", group,
                      selector=_selector_profile_find_group("name", group))
    group_id = group["id"]
    group_name = group["profile"]["name"]
    app_id = app['id']
    app_label = app["label"]
    okta_manager.call_okta_raw(f"/apps/{app_id}/groups/{group_id}", REST.delete)
    return f"App {app_id} ({app_label}) removed from group {group_id} ({group_name})"


@cli_apps.command(name="groups", context_settings=CONTEXT_SETTINGS)
@click.argument("app")
@_output_type_command_wrapper(None)
def apps_groups(app, **kwargs):
    """List the groups associated to an app"""
    app = _okta_get("apps", app,
                    selector=_selector_field_find("label", app))
    app_id = app['id']
    rv = okta_manager.call_okta(f"/apps/{app_id}/groups", REST.get)
    rv.sort(key=lambda x: x["id"])
    return rv


@click.group(name="users")
def cli_users():
    """Add, update (etc.) users"""
    pass


@cli_users.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.option("-m", "--match", 'matches', multiple=True,
              metavar="FIELD=VALUE",
              help="Filter for field values")
@click.option("-p", "--partial", is_flag=True,
              help="Accept partial matches for match queries.")
@click.option("-f", "--filter", 'filter_query', default="",
              help="Add Okta filter query")
@click.option("-s", "--search", 'search_query', default="",
              help="Add Okta search query")
@click.option("-q", "--query", 'q_query', default="",
              help="Add Okta query string")
@click.option("-d", "--deprovisioned", "deprov", default=False, is_flag=True,
              help="Return only deprovisioned users")
@_output_type_command_wrapper("id,status,profile.login,profile.firstName,"
                              "profile.lastName,profile.email")
def users_list(matches, partial, filter_query, search_query, q_query, deprov, **kwargs):
    """Lists users (all or using various filters)

    \b
    NOTES:
    * Does not contain deprovisioned users.
    * '-q' is fast but case-sensitive search over multiple fields
    * '-m' is a slow but case insensitive on a SINGLE field

    \b
    EXAMPLES:
    okta-cli users list -q Müller -m firstName=Hans
    okta-cli users list -f 'profile.site eq "Berlin"'

    \b
    This is equivalent:
    okta-cli users list -s 'status eq "DEPROVISIONED"'
    okta-cli users list -d

    \b
    See here for more info:
        https://is.gd/RrYDOY
    """
    params = {}
    if deprov:
        search_query = " and ".join(
            filter(None, (search_query, "status eq \"DEPROVISIONED\""))
        )
    if search_query:
        params["search"] = search_query
    if filter_query:
        params["filter"] = filter_query
    if q_query:
        params["q"] = q_query
    rv = _okta_retrieve("users", None, **params)
    filters_dict = {("profile." + k): v
                    for k, v in map(lambda x: x.split("=", 1), matches)}
    rv = filter_dicts(rv, filters=filters_dict, partial=partial)
    # filter_dicts returns a filter object, so "rv.sort()" throws
    # an exception. let's use "rv = sorted(rv, ...)" to fix this.
    rv = sorted(rv, key=lambda x: x["profile"]["login"])
    return rv


@cli_users.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument('lookup_value')
@click.option("-f", "--field", default="login",
              help="Look users up using this profile field (default: 'login')")
@_output_type_command_wrapper("id,status,profile.login,profile.firstName,"
                              "profile.lastName,profile.email")
def users_get(lookup_value, field, **kwargs):
    """Get one user uniquely using any profile field or ID"""
    rv = None
    if lookup_value[0] == "0" and len(lookup_value) == 20:
        try:
            # let's always return a list. the /users/ID will otherwise return
            # a dict.
            rv = [okta_manager.call_okta(f"/users/{lookup_value}", REST.get), ]
        except RequestsHTTPError as e:
            pass
    if rv is None:
        query = f'profile.{field} eq "{lookup_value}"'
        rv = okta_manager.list_users(search_query=query)
    len_rv = len(rv)
    if len_rv == 0:
        raise ExitException(f"No user found with {field}={lookup_value}")
    elif len_rv > 1:
        raise ExitException(f"Criteria not unique, found {len_rv} matches")
    return rv[0]


@cli_users.command(name="groups", context_settings=CONTEXT_SETTINGS)
@click.argument("user")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@_output_type_command_wrapper("id,profile.name,profile.description")
def users_groups(user, user_lookup_field, **kwargs):
    """List all groups belonging to a user"""
    user_obj = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user_obj["id"]
    rv = okta_manager.call_okta(f"/users/{user_id}/groups", REST.get)
    rv.sort(key=lambda x: x["profile"]["name"])
    return rv

@cli_users.command(name="apps", context_settings=CONTEXT_SETTINGS)
@click.argument("user")
@click.option("-f", "--user-lookup-field",
              metavar="FIELDNAME",
              default="login",
              help="Users are matched against the ID or this profile field; default: 'login'.")
@_output_type_command_wrapper("appInstanceId,appName,label")
def users_apps(user, user_lookup_field, **kwargs):
    """List all apps associated with a user"""
    user_obj = _okta_get("users", user,
                     search=f"profile.{user_lookup_field} eq \"{user}\"")
    user_id = user_obj["id"]
    rv = okta_manager.call_okta(f"/users/{user_id}/appLinks", REST.get)
    rv.sort(key=lambda x: x["label"])
    return rv


@cli_users.command(name="deactivate", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-e", "--send-email", is_flag=True,
              help="Send email to admins if set")
@click.option("--no-confirmation", is_flag=True,
              help="Don't ask - DANGER!!")
@_command_wrapper
def users_deactivate(login_or_id, send_email, no_confirmation):
    """Deactivate a user (DESTRUCTIVE OPERATION)"""
    if not no_confirmation:
        check = input("DANGER!! Do you REALLY want to do this "
                      "(maybe use 'suspend' instead)?\n"
                      f"Then enter '{login_or_id}': ")
        if check != login_or_id:
            raise ExitException("Aborted.")
    okta_manager.deactivate_user(login_or_id, send_email)
    return f"User {login_or_id} deactivated."


@cli_users.command(name="activate", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-e", "--send-email", is_flag=True,
              help="Send email to admins if set")
@_output_type_command_wrapper(None)
def users_activate(login_or_id, send_email, **kwargs):
    """Activate a user"""
    return okta_manager.activate_user(login_or_id, send_email)


@cli_users.command(name="unlock", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@_command_wrapper
def users_unlock(login_or_id):
    """Unlock a locked user"""
    okta_manager.call_okta(f"/users/{login_or_id}/lifecycle/unlock", REST.post)
    return f"User '{login_or_id}' unlocked."


@cli_users.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-e", "--send-email", is_flag=True,
              help="Send email to admins if set")
@click.option("--no-confirmation", is_flag=True,
              help="Don't ask - DANGER!!")
@_command_wrapper
def users_delete(login_or_id, send_email, no_confirmation):
    """Delete a user (DESTRUCTIVE OPERATION)"""
    if not no_confirmation:
        check = input("DANGER!! Do you REALLY want to do this?\n"
                      f"Then enter '{login_or_id}': ")
        if check != login_or_id:
            raise ExitException("Aborted.")
    okta_manager.delete_user(login_or_id, send_email)
    # .delete_user() does not return anything
    return f"User {login_or_id} deleted."


@cli_users.command(name="suspend", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@_command_wrapper
def users_suspend(login_or_id):
    """Suspend a user"""
    path = f"/users/{login_or_id}/lifecycle/suspend"
    rv = okta_manager.call_okta(path, REST.post)
    return rv


@cli_users.command(name="update", context_settings=CONTEXT_SETTINGS)
@click.argument('user_id')
@click.option('-s', '--set', 'set_fields', multiple=True)
@click.option('-S', '--array-set', 'set_array', multiple=True)
@click.option('-c', '--context', default=None,
              help="Set a context (profile, credentials) to save typing")
@_command_wrapper
def users_update(user_id, set_fields, set_array, context):
    """Update a user object.

    See https://is.gd/DWHEvA for details.

    This is equivalent:

    \b
    okta-cli users update 012345 -s profile.lastName=Doe
    okta-cli users update 012345         -s lastName=Doe -c profile

    EXAMPLE: Update a STRING profile field:

    \b
    okta-cli users update 012345 \\
       -s profile.email=me@myself.com

    EXAMPLE: Update an ARRAY profile field:

    \b
    okta-cli users update 012345 \\
       -S profile.customMultipleChoiceField=choice1,choice3

    EXAMPLE: Set a new password:

    \b
    okta-cli users update 012345 \\
       -s credentials.password.value="SoopaS3cret!"

    EXAMPLE: Update a recovery question:

    \b
    okta-cli users update 012345 \\
       -p credentials.recovery_question \\
       -s question="Who let the dogs out?" \\
       -s answer="Me."
    """
    fields_dict = {k: v for k, v in map(lambda x: x.split("=", 1), set_fields)}
    arrays_dict = {k: list(map(lambda x: x.strip(), v.split(",")))
                      for k, v in map(lambda x: x.split("=", 1), set_array)}
    fields_dict = {**fields_dict, **arrays_dict}
    if context:
        fields_dict = {context + "." + k: v for k, v in fields_dict.items()}
    nested_dict = _dict_flat_to_nested(fields_dict)
    return okta_manager.update_user(user_id, nested_dict)


@cli_users.command(name="bulk-update", context_settings=CONTEXT_SETTINGS)
@click.argument('file')
@click.option('-s', '--set', 'set_fields', multiple=True,
              help="Set default field values for updates")
@click.option('-i', '--jump-to-index', metavar="IDX",
              default=0,
              help="Start with index IDX (0-based) and skip previous entries")
@click.option('-u', '--jump-to-user', metavar="USER_ID",
              default=None,
              help="Same as --jump-to-index, but starts from a specific user "
                   "ID instead of an index")
@click.option('-l', '--limit', metavar="NUM",
              default=0,
              help="Stop after NUM updates")
@click.option('-w', '--workers', metavar="NUM",
              default=25,
              help="use this many threads parallel, default:25")
@_command_wrapper
def users_bulk_update(file, set_fields, jump_to_index, jump_to_user, limit,
                      workers):
    """
    Bulk-update users from a CSV or Excel (.xlsx) file

    The CSV file *must* contain a "profile.login" OR an "id" column.

    All columns which do not contain a dot (".") are ignored. You can only
    update fields of sub-structures, not top level fields in okta (e.g. you
    *can* update "profile.site", but you *cannot* update "id").
    """

    def excel_reader():
        wb = load_workbook(filename=file)
        rows = wb.active.rows

        # Get the header values as keys and move the iterator to the next item
        keys = [c.value for c in next(rows)]
        num_keys = len(keys)
        for row in rows:
            values = [c.value for c in row]
            rv = dict(zip(keys, values[:num_keys]))
            if any(rv.values()):
                yield rv

    def csv_reader():
        with open(file, "r", encoding="utf-8") as infile:
            dialect = csv.Sniffer().sniff(infile.read(4096))
            infile.seek(0)
            dr = csv.DictReader(infile, dialect=dialect)
            for row in dr:
                if any(row.values()):
                    yield row

    def file_reader():
        dr = excel_reader() \
            if splitext(file)[1].lower() == ".xlsx" else csv_reader()
        if jump_to_user:
            tmp = next(dr)
            while jump_to_user not in (
                    tmp.get("profile.login", ""), tmp.get("id", "")):
                tmp = next(dr)
        elif jump_to_index:
            # prevent both being used at the same time :)
            for _ in range(jump_to_index):
                next(dr)
        _cnt = 0
        for row in dr:
            if limit and _cnt == limit:
                break
            yield row
            _cnt += 1

    def update_user_parallel(_row, index):
        user_id = None

        # this is a closure, let's use the outer scope's variables
        # Set preference to "id" first
        for field in ("id", "profile.login"):
            if field in _row and user_id is None:
                user_id = _row.pop(field)
        # you can't set top-level fields. pop all of them.
        _row = {k: v for k, v in _row.items() if k.find(".") > -1}
        # fields_dict - from outer scope.
        final_dict = _dict_flat_to_nested(_row, defaults=fields_dict)

        # user_id check
        if user_id is None:
            upd_err.append((
                index + jump_to_index,
                final_dict,
                "missing user_id column (id or profile.login)"
            ))
            return

        try:
            upd_ok.append(okta_manager.update_user(user_id, final_dict))
        except RequestsHTTPError as e:
            upd_err.append((index + jump_to_index, final_dict, str(e)))

    print("Bulk update might take a while. Please be patient.", flush=True)

    upd_ok = []
    upd_err = []
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    dr = file_reader()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        runs = {idx: ex.submit(update_user_parallel, row, idx)
                for idx, row in enumerate(dr)}
        for job in as_completed(runs.values()):
            pass

    print(f"{len(runs)} - done.", file=sys.stderr)
    tmp = {"ok": upd_ok, "errors": upd_err}
    timestamp_str = dt.now().strftime("%Y%m%d_%H%M%S")
    rv = ""
    for name, results in tmp.items():
        if len(results):
            file_name = f"okta-bulk-update-{timestamp_str}-{name}.json"
            with open(file_name, "w") as outfile:
                outfile.write(json.dumps(results, indent=2, sort_keys=True))
                rv += f"{len(results):>4} {name:6} - {file_name}\n"
        else:
            rv += f"{len(results):>4} {name:6}\n"
    return rv + f"{len(upd_ok) + len(upd_err)} total"


@cli_users.command(name="add", context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--set', 'set_fields', metavar="FIELD=value",
              help="set any user object field",
              multiple=True)
@click.option('-p', '--profile', 'profile_fields', metavar="FIELD=value",
              help="same as '-s profile.FIELD=value'",
              multiple=True)
@click.option('-g', '--group', 'groups', metavar="GROUP_ID",
              help="specify groups the user should be added to on creation",
              multiple=True)
@click.option('--activate/--no-activate', default=True,
              help="Set 'activation' flag, default: True")
@click.option('--provider/--no-provider', default=False,
              help="Set 'provider' flag, default: False")
@click.option('--nextlogin/--no-nextlogin', default=False,
              help="User must change password, default: False")
@_command_wrapper
def users_add(set_fields, profile_fields, groups, activate, provider,
              nextlogin):
    """Add a user to Okta

    Note that this is equivalent:

    \b
    users add -s profile.login=mylogin
    users add -p login=mylogin
    (-p profile.SETTING overrides -s SETTING if both are given)

    You can also set a password upon creation:

    \b
    users add -s credentials.password.value=my.super-password

    Okta documentation: https://is.gd/aUtkTo
    """
    # create user dict
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    profile_dict = {"profile." + k: v
                    for k, v in map(lambda x: x.split("="), profile_fields)}
    fields_dict.update(profile_dict)
    if groups:
        fields_dict["groupIds"] = groups

    # query parameters
    params = {
        'activate': "True" if activate else "False",
        'provider': "True" if provider else "False",
    }
    if nextlogin:
        params['nextlogin'] = "changePassword"

    # when reading from csv, we iterate
    final_dict = _dict_flat_to_nested(fields_dict)
    return okta_manager.add_user(params, final_dict)


@click.group(name="features")
def cli_features():
    """Feature operations"""
    pass


@cli_features.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@click.option("-m", "--match", 'matches', multiple=True)
@click.option("-p", "--partial", is_flag=True, default=True,
              help="Accept partial matches for match queries.")
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_list(partial_name, partial_name_field, matches, partial, **kwargs):
    """Lists tenant features"""
    selector = None
    if partial_name:
        selector=_selector_field_find(partial_name_field, partial_name)
    rv = _okta_retrieve("features", None, selector=selector)
    filters_dict = {k: v for k, v in map(lambda x: x.split("="), matches)}
    rv = filter_dicts(rv, filters=filters_dict, partial=partial)
    rv = sorted(rv, key=lambda x: x["name"])
    return rv


@cli_features.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_get(partial_name, partial_name_field, **kwargs):
    """Retrieves information about one specific feature"""
    rv = _okta_get("features", partial_name,
                   selector=_selector_field_find(partial_name_field, partial_name))
    return rv


@cli_features.command(name="enable", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@click.option("--force", 'force', is_flag=True, default=False)
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_enable(partial_name, partial_name_field, force, **kwargs):
    """Enable a feature"""
    mode = "enable"
    params = {"mode": "force"} if force else None
    feature = _okta_get("features", partial_name,
                        selector=_selector_field_find(partial_name_field, partial_name))
    feature_id = feature["id"]
    rv = okta_manager.call_okta(f"/features/{feature_id}/{mode}",
                                REST.post, params=params)
    return rv


@cli_features.command(name="disable", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@click.option("--force", 'force', is_flag=True, default=False)
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_disable(partial_name, partial_name_field, force, **kwargs):
    """Disable a feature"""
    mode = "disable"
    params = {"mode": "force"} if force else None
    feature = _okta_get("features", partial_name,
                        selector=_selector_field_find(partial_name_field, partial_name))
    feature_id = feature["id"]
    rv = okta_manager.call_okta(f"/features/{feature_id}/{mode}",
                                REST.post, params=params)
    return rv


@cli_features.command(name="dependents", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@click.option("--force", 'force', is_flag=True, default=False)
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_dependents(partial_name, partial_name_field, force, **kwargs):
    """List features depending on this one"""
    mode = "dependents"
    params = {"mode": "force"} if force else None
    feature = _okta_get("features", partial_name,
                        selector=_selector_field_find(partial_name_field, partial_name))
    feature_id = feature["id"]
    rv = okta_manager.call_okta(f"/features/{feature_id}/{mode}", REST.get)
    rv.sort(key=lambda x: x["name"])
    return rv


@cli_features.command(name="dependencies", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--partial-name-field", 'partial_name_field', default="name")
@click.option("--force", 'force', is_flag=True, default=False)
@_output_type_command_wrapper("id,status,stage.value,type,name")
def features_dependencies(partial_name, partial_name_field, force, **kwargs):
    """List dependencies of this feature"""
    mode = "dependencies"
    feature = _okta_get("features", partial_name,
                        selector=_selector_field_find(partial_name_field, partial_name))
    feature_id = feature["id"]
    rv = okta_manager.call_okta(f"/features/{feature_id}/{mode}", REST.get)
    rv.sort(key=lambda x: x["name"])
    return rv


@click.group(context_settings=CONTEXT_SETTINGS)
def cli_main():
    """
    Okta CLI helper.

    See subcommands for help: "okta-cli users --help" etc.

    If in doubt start with: "okta-cli config new --help"
    """
    pass


@cli_main.command(name="dump", context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--dir', 'target_dir',
              help="Save in this directory", default=None)
@click.option("--no-user-list", is_flag=True)
@click.option("--no-app-users", is_flag=True)
@click.option("--no-group-users", is_flag=True)
@_command_wrapper
def dump(target_dir, no_user_list, no_app_users, no_group_users):
    """
    Dump basically everything into CSV files for further processing

    NOTE: In contrast to 'users list' the 'dump' command will include
    users in the DEPROVISIONED state by default.
    """

    def save_in(save_dir, save_file, obj):
        if not isdir(save_dir):
            mkdir(save_dir)
        final_file = join(save_dir, save_file)
        with open(final_file, "w") as outfile:
            _dump_csv(obj, out=outfile)

    def save_in_csv(save_dir, save_file, obj, headers):
        if not isdir(save_dir):
            mkdir(save_dir)
        final_file = join(save_dir, save_file)
        with open(final_file, "w") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(headers)
            for row in obj:
                writer.writerow(row)

    def get_users_for(obj_list, rest_path, workers=1):
        table = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            runs = {
                ex.submit(okta_manager.call_okta,
                          f"/{rest_path}/{obj['id']}/users",
                          REST.get,
                          params={"limit": 1000}):
                    obj["id"]
                for obj in obj_list}
            for result in runs:
                gid = runs[result]
                table += [(gid, u["id"]) for u in result.result()]
        return table

    default_workers = 25

    if target_dir is None:
        target_dir = dt.strftime(dt.now(), "okta-dump-%Y%m%d%H%M%S")

    print("Please be patient, this can take several minutes.")

    if no_user_list:
        print("Skipping list of users.")
    else:
        print("Saving user list ... ", end="", flush=True)
        dump_me = okta_manager.list_users()
        # deprovisioned users are NOT included in the listing by default
        tmp_str = "status eq \"DEPROVISIONED\""
        dump_me += okta_manager.list_users(search_query=tmp_str)
        save_in(target_dir, "users.csv", dump_me)
        print("done.")

    for func, what, no_detail in (
            (okta_manager.list_groups, "group", no_group_users),
            (okta_manager.list_apps, "app", no_app_users)
    ):
        print(f"Saving {what} list ... ", end="", flush=True)
        dump_me = func()
        save_in(target_dir, f"{what}s.csv", dump_me)
        print("done.")

        if no_detail:
            print(f"Skipping list of {what} users.")
        else:
            print(f"Saving {what} users ... ", end="", flush=True)
            table = get_users_for(dump_me, f"{what}s", workers=default_workers)
            save_in_csv(target_dir, f"{what}_users.csv", table, (what, "user"))
            print("done.")


@cli_main.command(name="raw", context_settings=CONTEXT_SETTINGS)
@click.argument('api_endpoint')
@click.option('-X', '--http-method',
              default="get", type=click.Choice(("get", "post", "put", "delete")),
              help="Which HTTP method to use; default: 'get'")
@click.option('-q', '--query', 'query_params', multiple=True,
              help="Set a query field in the URL, format field=value")
@click.option('-b', '--body', 'body',
              default=None,
              help="Specify message body, use FILE:<filename> to read from file")
@click.option('--base-path', 'base_path',
              default=None,
              help="Specify a different base path than the default (/api/v1)")
@_output_type_command_wrapper(None)
def raw(api_endpoint, http_method, query_params, body, base_path, **kwargs):
    """Perform a request against the specified API endpoint"""
    methods = {
        "get":    REST.get,
        "post":   REST.post,
        "delete": REST.delete,
        "put":    REST.put,
    }
    use_method = methods[http_method.lower()]
    if base_path and not base_path.startswith("/"):
        base_path = "/" + base_path
    if not api_endpoint.startswith("/"):
        api_endpoint = "/" + api_endpoint
    p_dict = dict(
        [(y[0], y[1]) for y in map(lambda x: x.split("=", 1), query_params)])
    if body:
        if body.startswith("FILE:"):
            use_body = json.loads(open(body[5:], "r").read())
        else:
            use_body = json.loads(body)
    else:
        use_body = None
    rv = okta_manager.call_okta(api_endpoint, use_method, params=p_dict, body_obj=use_body,
                                custom_path_base=base_path)
    return rv


@cli_main.command(name="version", context_settings=CONTEXT_SETTINGS)
def cli_version():
    """Print version number and exit"""
    print(VERSION)


@click.group(name="eventhooks")
def cli_eventhooks():
    """Event hook operations"""
    pass


@cli_eventhooks.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_list(partial_name, **kwargs):
    """Lists event hooks"""
    partial_name_field = "name"
    selector = None
    if partial_name:
        selector=_selector_field_find(partial_name_field, partial_name)
    rv = _okta_retrieve("eventHooks", None, selector=selector)
    return rv


@cli_eventhooks.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_get(partial_name, **kwargs):
    """Retrieves information about one specific feature"""
    partial_name_field = "name"
    rv = _okta_get("eventHooks", partial_name,
                   selector=_selector_field_find(partial_name_field, partial_name))
    return rv


def get_event_object(url, name, events):
    """Either creates or updates the event (POST or PUT), depending on
    method"""
    # see here: https://stackoverflow.com/a/952952/902327
    events = [item for e in events for item in e.split(",")]
    event_obj = {
        "name": name,
        "events": {
            "type": "EVENT_TYPE",
            "items": events,
        },
        "channel": {
            "type": "HTTP",
            "version": "1.0.0",
            "config": {
                "uri": url,
            }
        }
    }
    return event_obj


@cli_eventhooks.command(name="add", context_settings=CONTEXT_SETTINGS)
@click.option("-u", "--url",
              required=True,
              help="The URL where the events will be sent to by Okta")
@click.option("-n", "--name",
              required=True,
              help="A short name (description) of the event hook")
@click.option("-e", "--event", "events",
              required=True, multiple=True,
              help="Specify event types (either separated by comma or multiple -e)")
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_add(url, name, events, **kwargs):
    """Creates a new event hook"""
    event_obj = get_event_object(url, name, events)
    return okta_manager.call_okta(f"/eventHooks", REST.post, body_obj=event_obj)


@cli_eventhooks.command(name="update", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=True, default=None)
@click.option("-u", "--url",
              required=True,
              help="The URL where the events will be sent to by Okta")
@click.option("-n", "--name",
              required=True,
              help="A short name (description) of the event hook")
@click.option("-e", "--event", "events",
              required=True, multiple=True,
              help="Specify event types (either separated by comma or multiple -e)")
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_update(partial_name, url, name, events, **kwargs):
    """Updates an event hook"""
    partial_name_field = "name"
    existing = _okta_get(
        "eventHooks", partial_name,
        selector=_selector_field_find(partial_name_field, partial_name)
    )
    existing_id = existing["id"]
    event_obj = get_event_object(url, name, events)
    return okta_manager.call_okta(f"/eventHooks/{existing_id}", REST.put, body_obj=event_obj)


@cli_eventhooks.command(name="activate", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=True)
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_activate(partial_name, **kwargs):
    """Activates an event hook"""
    partial_name_field = "name"
    existing = _okta_get(
        "eventHooks", partial_name,
        selector=_selector_field_find(partial_name_field, partial_name)
    )
    existing_id = existing["id"]
    return okta_manager.call_okta_raw(
        f"/eventHooks/{existing_id}/lifecycle/deactivate",
        REST.post
    )


@cli_eventhooks.command(name="verify", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=True)
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_verify(partial_name, **kwargs):
    """Verifies an event hook"""
    partial_name_field = "name"
    existing = _okta_get(
        "eventHooks", partial_name,
        selector=_selector_field_find(partial_name_field, partial_name)
    )
    existing_id = existing["id"]
    return okta_manager.call_okta(
        f"/eventHooks/{existing_id}/lifecycle/verify",
        REST.post
    )


@cli_eventhooks.command(name="deactivate", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=True)
@_output_type_command_wrapper("id,created,status,verificationStatus,name")
def eventhook_deactivate(partial_name, **kwargs):
    """Deactivates an event hook"""
    partial_name_field = "name"
    existing = _okta_get(
        "eventHooks", partial_name,
        selector=_selector_field_find(partial_name_field, partial_name)
    )
    existing_id = existing["id"]
    existing_name = existing["name"]
    return okta_manager.call_okta(
        f"/eventHooks/{existing_id}/lifecycle/deactivate",
        REST.post
    )


@cli_eventhooks.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=True)
@_command_wrapper
def eventhook_delete(partial_name, **kwargs):
    """Deactivates an event hook"""
    partial_name_field = "name"
    existing = _okta_get(
        "eventHooks", partial_name,
        selector=_selector_field_find(partial_name_field, partial_name)
    )
    existing_id = existing["id"]
    existing_name = existing["name"]
    okta_manager.call_okta_raw(
        f"/eventHooks/{existing_id}",
        REST.delete
    )
    return f"event hook {existing_id} ({existing_name}) deleted"



cli_main.add_command(cli_config)
cli_main.add_command(cli_users)
cli_main.add_command(cli_pw)
cli_main.add_command(cli_groups)
cli_main.add_command(cli_apps)
cli_main.add_command(cli_features)
cli_main.add_command(cli_eventhooks)
